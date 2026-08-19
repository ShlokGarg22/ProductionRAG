from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.config import settings
from app.services.retrieval.embeddings import embed_texts
from fastembed import SparseTextEmbedding

# Initialize Sparse Model globally so it is only loaded once
sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")

qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
)

def search_enterprise_knowledge(query: str, limit: int = 30):
    """
    Embeds the user query and searches the Qdrant vector database using Hybrid Search (Dense + Sparse).
    """
    # Embed the query string into a dense vector
    query_dense_vector = embed_texts([query])[0]
    
    # Embed the query string into a sparse vector
    sparse_vec = list(sparse_model.embed([query]))[0]
    query_sparse_vector = models.SparseVector(
        indices=sparse_vec.indices.tolist(),
        values=sparse_vec.values.tolist()
    )
    
    # Perform Hybrid Search using Reciprocal Rank Fusion (RRF)
    response = qdrant_client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        prefetch=[
            models.Prefetch(
                query=query_dense_vector,
                using="dense",
                limit=limit
            ),
            models.Prefetch(
                query=query_sparse_vector,
                using="sparse",
                limit=limit
            )
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit
    )
    
    # Format the results
    results = []
    for hit in response.points:
        results.append({
            "content": hit.payload.get("text", ""),
            "score": hit.score,
            "source": hit.payload.get("source", "Unknown")
        })
    
    return results
