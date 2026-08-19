import time
import os
import sys

# Ensure we can import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.llm import get_fast_llm, get_llm
from app.guardrails.service import guard, initialize_rails
from app.services.retrieval.qdrant_service import search_enterprise_knowledge
from app.services.retrieval.ranking_service import rerank_documents

def benchmark():
    print("Initializing Guardrails...")
    initialize_rails()
    
    print("\n--- Benchmarking Azure Fast LLM ---")
    t0 = time.time()
    fast_llm = get_fast_llm()
    fast_llm.invoke("Say hi")
    print(f"Azure Fast LLM time: {time.time() - t0:.2f}s")
    
    print("\n--- Benchmarking Azure Slow LLM ---")
    t0 = time.time()
    slow_llm = get_llm()
    slow_llm.invoke("Say hi")
    print(f"Azure Slow LLM time: {time.time() - t0:.2f}s")
    
    print("\n--- Benchmarking NeMo Guardrails ---")
    t0 = time.time()
    guard("how does kubernetes networking work?")
    print(f"NeMo Guardrails time: {time.time() - t0:.2f}s")
    
    print("\n--- Benchmarking Qdrant Search ---")
    t0 = time.time()
    docs = search_enterprise_knowledge("kubernetes networking", limit=15)
    print(f"Qdrant time: {time.time() - t0:.2f}s (found {len(docs)} docs)")
    
    print("\n--- Benchmarking Jina Reranking ---")
    if docs:
        t0 = time.time()
        rerank_documents("kubernetes networking", docs, top_n=5)
        print(f"Jina Reranking time: {time.time() - t0:.2f}s")
    else:
        print("Skipped Jina (no docs)")

if __name__ == "__main__":
    benchmark()
