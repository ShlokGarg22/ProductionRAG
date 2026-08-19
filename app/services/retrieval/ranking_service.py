import requests
import logfire
from app.config import settings

def rerank_documents(query: str, docs: list[dict], top_n: int = 5) -> list[dict]:
    """
    Reranks documents retrieved from vector DB to push the most relevant to the top
    using the external Jina AI Reranker API.
    """
    if not docs:
        return []

    # Extract contents for Jina AI
    doc_contents = [doc['content'] for doc in docs]

    # Prepare request for Jina AI
    url = "https://api.jina.ai/v1/rerank"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.JINA_API_KEY}"
    }
    payload = {
        "model": "jina-reranker-v3.5",
        "query": query,
        "top_n": top_n,
        "documents": doc_contents
    }

    try:
        with logfire.span("Jina AI Reranking"):
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            # Jina returns documents sorted by relevance score
            reranked_docs = []
            for item in data.get("results", []):
                idx = item.get("index")
                reranked_docs.append(docs[idx])
                
            return reranked_docs
    except (requests.exceptions.Timeout, Exception) as e:
        logfire.error(f"Jina AI Reranking failed: {e}")
        # Fallback to the original order if API fails
        return docs[:top_n]
