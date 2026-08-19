import os
import sys

# Ensure the app module can be found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.retrieval.qdrant_service import search_enterprise_knowledge
from app.services.retrieval.ranking_service import rerank_documents

def test_retrieval():
    print("==================================================")
    print("TESTING HYBRID SEARCH & JINA RERANKING")
    print("==================================================\n")
    
    test_query = "What is the main topic of the documents?"
    
    print(f"Executing Hybrid Search (Dense + Sparse BM25) for query: '{test_query}'...")
    try:
        # Step 1: Hybrid Search (fetches Top 30)
        initial_results = search_enterprise_knowledge(test_query, limit=30)
        
        if not initial_results:
            print("\nNO DATA FOUND in Qdrant collection!")
            print("Please ensure your ingestion script ran successfully.")
            return

        print(f"\nHybrid Search returned {len(initial_results)} chunks.")
        print("\nTop 3 Hybrid Results (Before Reranking):")
        for i, res in enumerate(initial_results[:3]):
            score = round(res.get('score', 0), 4)
            source = res.get('source', 'Unknown')
            content = res.get('content', '')[:100].replace('\n', ' ')
            print(f"  {i+1}. [Score: {score}] (Source: {source}) -> {content}...")
            
        # Step 2: Jina Reranking
        print("\n\nExecuting Jina AI Reranker (Top 5)...")
        doc_contents = [res["content"] for res in initial_results]
        reranked_docs = rerank_documents(test_query, doc_contents, top_n=5)
        
        print(f"\nJina AI successfully returned {len(reranked_docs)} highly relevant chunks.")
        print("\nTop 3 Reranked Results (Final Context sent to LLM):")
        for i, doc in enumerate(reranked_docs[:3]):
            content = doc[:100].replace('\n', ' ')
            print(f"  {i+1}. -> {content}...")

    except Exception as e:
        print(f"\nError during retrieval: {e}")

if __name__ == "__main__":
    test_retrieval()
