import json
import os
import logfire
from redisvl.index import SearchIndex
from redisvl.query import VectorQuery
from langchain_openai import AzureOpenAIEmbeddings
from app.config import settings

# Initialize Embeddings Model (Direct to Azure, bypassing Portkey for Embeddings)
embeddings = AzureOpenAIEmbeddings(
    azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "text-embedding-3-small"),
    openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY")
)

# Define RedisVL Schema for our Cache
schema = {
    "index": {
        "name": "semantic_cache_v2",
        "prefix": "cache_doc_v2",
        "storage_type": "hash"
    },
    "fields": [
        {"name": "query", "type": "text"},
        {"name": "response_data", "type": "text"}, # Renamed from payload to avoid redis-py kwargs conflict
        {
            "name": "embedding",
            "type": "vector",
            "attrs": {
                "dims": 1536, # text-embedding-3-small dimensions
                "distance_metric": "cosine",
                "algorithm": "flat",
                "datatype": "float32"
            }
        }
    ]
}

# Connect to Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
index = SearchIndex.from_dict(schema)

# Will be initialized in the main FastAPI startup event
def init_cache():
    try:
        index.connect(REDIS_URL)
        index.create(overwrite=False)
        logfire.info("Redis Semantic Cache Initialized")
    except Exception as e:
        logfire.error(f"Failed to connect to Redis Semantic Cache: {e}")

def check_semantic_cache(query: str):
    """
    Searches Redis for a semantically identical query (cosine distance < 0.05).
    Returns the cached JSON payload if found, else None.
    """
    try:
        # Generate embedding for the incoming query
        vector = embeddings.embed_query(query)
        
        # Build Vector Query
        v_query = VectorQuery(
            vector=vector,
            vector_field_name="embedding",
            return_fields=["response_data", "query"],
            num_results=1
        )
        
        # Execute Search
        results = index.query(v_query)
        
        if results:
            best_match = results[0]
            # distance is returned as vector_distance
            distance = float(best_match.get("vector_distance", 1.0))
            if distance < 0.05: # 95%+ similarity threshold
                logfire.info(f"Semantic Cache HIT! Matched with: '{best_match['query']}' (Distance: {distance:.4f})")
                return json.loads(best_match["response_data"])
            else:
                logfire.info(f"Semantic Cache MISS. Best match '{best_match['query']}' was not close enough (Distance: {distance:.4f})")
        else:
            logfire.info("Semantic Cache MISS. Cache is empty.")
            
        return None
    except Exception as e:
        logfire.error(f"Cache Search Error: {e}")
        return None

import numpy as np

def save_to_cache(query: str, payload_dict: dict):
    """
    Saves the query, payload, and vector embedding to Redis.
    """
    try:
        vector = embeddings.embed_query(query)
        # Redis Hash storage requires vectors to be converted to raw bytes
        vector_bytes = np.array(vector, dtype=np.float32).tobytes()
        
        record = {
            "query": query,
            "response_data": json.dumps(payload_dict),
            "embedding": vector_bytes
        }
        index.load([record])
        logfire.info("Saved response to Semantic Cache")
    except Exception as e:
        logfire.error(f"Cache Save Error: {e}")
