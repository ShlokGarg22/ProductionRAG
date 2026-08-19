import os
import sys
# Ensure the root directory is on the path so 'from app.config import settings' works
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import uuid
import json
import logfire
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.config import settings
from app.services.retrieval.embeddings import embed_texts, get_embedding_dim
from app.ingestion.loaders.pdf import parse_pdf
from app.ingestion.loaders.html import parse_html
from app.ingestion.loaders.text import parse_text
from app.ingestion.chunking.splitter import chunk_text
from fastembed import SparseTextEmbedding

# Initialize Sparse Model globally so it is only loaded once
sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")

logfire.configure(
    service_name="enterprise-ingestion-service",
    token=os.getenv("LOGFIRE_TOKEN")
)

# Local folder where parsed + chunked JSON metadata is saved (replaces GCS processed bucket)
PROCESSED_DATA_DIR = "processed_data"

# Initialize Qdrant Client
qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
)


def save_processed_locally(data: dict, source_type: str, filename: str) -> str:
    """Save parsed chunk metadata as JSON in processed_data/<source_type>/."""
    folder = os.path.join(PROCESSED_DATA_DIR, source_type)
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, f"{filename}.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return dest


def process_file(file_path: str, filename: str, source_type: str) -> bool:
    """Parse → chunk → save locally → embed → index in Qdrant. Returns True if successful, False otherwise."""
    with logfire.span("Processing File", file=filename, source=source_type):
        try:
            # 1. Extract text based on file extension
            ext = filename.lower().rsplit(".", 1)[-1]
            if ext == "pdf":
                full_text = parse_pdf(file_path)
            elif ext in ("html", "htm"):
                full_text = parse_html(file_path)
            elif ext == "txt":
                full_text = parse_text(file_path)
            elif ext in ("docx", "pptx"):
                from app.ingestion.loaders.office import parse_office
                full_text = parse_office(file_path)
            else:
                logfire.warning(f"Skipping unsupported file type: {filename}")
                return False

            if not full_text or not full_text.strip():
                logfire.warning(f"No text extracted from {filename} — skipping.")
                return False

            # 2. Chunk text
            chunks = chunk_text(full_text)
            if not chunks:
                return False

            # 3. Save processed metadata locally
            processed_data = {
                "filename": filename,
                "source_type": source_type,
                "chunks": chunks,
            }
            local_path = save_processed_locally(processed_data, source_type, filename)
            logfire.info(f"Saved processed data -> {local_path}")

            # 4. Embed and index in Qdrant
            with logfire.span("Vectorizing & Indexing"):
                embeddings = embed_texts(chunks)
                sparse_embeddings = list(sparse_model.embed(chunks))
                
                points = [
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector={
                            "dense": vector,
                            "sparse": models.SparseVector(
                                indices=sparse_vec.indices.tolist(),
                                values=sparse_vec.values.tolist()
                            )
                        },
                        payload={
                            "text": chunk,
                            "source": filename,
                            "source_type": source_type,
                        },
                    )
                    for chunk, vector, sparse_vec in zip(chunks, embeddings, sparse_embeddings)
                ]

                qdrant_client.upsert(
                    collection_name=settings.QDRANT_COLLECTION,
                    points=points,
                )
                logfire.info(f"Indexed {len(points)} points to Qdrant from {filename}.")

            return True

        except Exception as e:
            logfire.error(f"Failed to process {filename}: {e}")
            return False


def process_directory(dir_path: str, source_type: str):
    """Process every file in a directory concurrently."""
    with logfire.span("Scanning Directory", path=dir_path, source=source_type):
        files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
        total_files = len(files)
        logfire.info(f"Found {total_files} files in {dir_path}.")
        
        success_count = 0
        failure_count = 0

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(process_file, os.path.join(dir_path, filename), filename, source_type): filename
                for filename in files
            }
            for future in as_completed(futures):
                filename = futures[future]
                try:
                    is_success = future.result()
                    if is_success:
                        success_count += 1
                    else:
                        failure_count += 1
                except Exception as e:
                    failure_count += 1
                    logfire.error(f"Concurrent file processing error for {filename}: {e}")
                    
        logfire.info(f"Directory processing complete.", total_files=total_files, success=success_count, failed=failure_count)


def run_universal_ingestion(base_dir: str, explicit_source_type: str = None, wipe: bool = False):
    """
    Scan base_dir, map sub-folders to source types, and ingest all documents.
    Pass --wipe to drop and recreate the Qdrant collection before ingestion.
    """
    with logfire.span("Universal Ingestion Started", base_directory=base_dir):

        # Wipe collection if requested
        if wipe:
            with logfire.span("Wiping Collection"):
                if qdrant_client.collection_exists(settings.QDRANT_COLLECTION):
                    qdrant_client.delete_collection(settings.QDRANT_COLLECTION)
                    logfire.info(f"Collection '{settings.QDRANT_COLLECTION}' deleted.")

        # Recreate collection — dimension resolved at runtime after embedding model probe
        if not qdrant_client.collection_exists(settings.QDRANT_COLLECTION):
            dim = get_embedding_dim()
            qdrant_client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config={
                    "dense": models.VectorParams(
                        size=dim,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    )
                }
            )
            logfire.info(
                f"Created collection '{settings.QDRANT_COLLECTION}' "
                f"({dim}-dim dense, sparse BM25 enabled)."
            )

        # Route to sub-folders or treat the whole dir as one source
        subdirs = [
            d for d in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, d))
        ]

        if not subdirs:
            if explicit_source_type:
                source_type = explicit_source_type
            else:
                base_name = os.path.basename(os.path.normpath(base_dir)).lower()
                source_type = (
                    "true" if "true" in base_name
                    else "noisy" if "noisy" in base_name
                    else "general"
                )
            logfire.info(f"No sub-folders found — processing '{base_dir}' as '{source_type}'.")
            process_directory(base_dir, source_type)
        else:
            for subdir in subdirs:
                source_type = (
                    "true" if "true" in subdir.lower()
                    else "noisy" if "noisy" in subdir.lower()
                    else subdir
                )
                process_directory(os.path.join(base_dir, subdir), source_type)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run universal ingestion pipeline.")
    parser.add_argument("target_dir", nargs="?", default="DATA", help="Target directory for ingestion")
    parser.add_argument("explicit_type", nargs="?", default=None, help="Explicit source type")
    parser.add_argument("--wipe", action="store_true", help="Wipe and recreate Qdrant collection")
    
    args = parser.parse_args()

    if not os.path.exists(args.target_dir):
        print(f"Error: path '{args.target_dir}' does not exist.")
        sys.exit(1)

    run_universal_ingestion(args.target_dir, explicit_source_type=args.explicit_type, wipe=args.wipe)
    logfire.info("Ingestion job completed.")
