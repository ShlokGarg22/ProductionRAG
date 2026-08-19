# Understanding the Ingestion Pipeline

The ingestion pipeline is the process of taking raw documents (PDFs, Word documents, text files), extracting their content, breaking them down into readable pieces, and storing them in a Vector Database (Qdrant) so that our AI can search through them later. 

Here is a step-by-step breakdown of how the ingestion pipeline in `krishnaik-rag` works.

---

## The 4 Main Steps

The main script controlling this flow is `app/ingestion/processor.py`. Whenever you run the processor, it executes four main steps for every single file it finds.

### Step 1: Text Extraction (Loaders)
The pipeline looks at the file extension and decides which "loader" to use. Loaders are dedicated scripts for extracting clean text from different file formats.

```python
# From app/ingestion/processor.py
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
```

**Example: PDF Extraction (`app/ingestion/loaders/pdf.py`)**
If the file is a PDF, it gets routed to the `parse_pdf` function. This function uses `pdf-inspector` to pull out markdown. 
> [!TIP]
> **Vision OCR Fallback:** If `pdf.py` detects that the PDF is just a scanned image without selectable text, it intelligently falls back to converting the PDF pages to images and uses an Azure OpenAI Vision model to visually "read" the text from the images!

### Step 2: Chunking
Language models and vector databases have limits on how much text they can process at once. We can't feed a 500-page book into a vector database as a single item.

```python
# From app/ingestion/processor.py
chunks = chunk_text(full_text)
```
The `chunk_text` function (located in `app/ingestion/chunking/splitter.py`) breaks the massive extracted text down into smaller, overlapping paragraphs (or "chunks"). This ensures that when the AI searches for an answer, it finds the specific relevant paragraphs rather than a massive wall of text.

### Step 3: Saving Processed Metadata Locally
Before we send anything to the database, we save a local backup of what the pipeline just did.

```python
# From app/ingestion/processor.py
processed_data = {
    "filename": filename,
    "source_type": source_type,
    "chunks": chunks,
}
local_path = save_processed_locally(processed_data, source_type, filename)
```
This saves a `.json` file inside the `processed_data/` directory. It contains the original filename, whether the data was clean or noisy, and the actual chunks. This is super helpful for debugging because you can look at the JSON file to see exactly how your document was broken up.

### Step 4: Embedding and Indexing (Qdrant)
This is where the AI magic happens. We convert the text chunks into numbers (vectors/embeddings) and save them to the Qdrant database.

```python
# From app/ingestion/processor.py

# 1. Convert chunks of text into vector numbers
embeddings = embed_texts(chunks) 

# 2. Package the text, the vector, and the metadata together
points = [
    models.PointStruct(
        id=str(uuid.uuid4()),
        vector=vector,
        payload={
            "text": chunk,
            "source": filename,
            "source_type": source_type,
        },
    )
    for chunk, vector in zip(chunks, embeddings)
]

# 3. Upload to Qdrant Vector Database
qdrant_client.upsert(
    collection_name=settings.QDRANT_COLLECTION,
    points=points,
)
```
- **Embedding:** `embed_texts()` uses your Azure OpenAI embedding model (`text-embedding-3-small` in your `.env`) to turn human text into a high-dimensional math array (a vector). Text that has similar meaning will have similar math arrays.
- **Indexing:** We package the vector and the raw text chunk together as a `PointStruct` and insert it into Qdrant using `qdrant_client.upsert()`. 

---

## How it Runs Fast (Concurrency)

If you have 1,000 files in your `DATA` folder, processing them one by one would take forever. The pipeline uses Python's `ThreadPoolExecutor` in the `process_directory` function.

```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(process_file, os.path.join(dir_path, filename), filename, source_type): filename
        for filename in files
    }
```
This tells Python to spin up 5 worker threads, meaning it processes 5 documents at the exact same time, significantly speeding up the ingestion process.
