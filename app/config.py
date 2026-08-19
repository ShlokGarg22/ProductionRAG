import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    # --- AZURE OPENAI ---
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
    AZURE_OPENAI_FAST_DEPLOYMENT = os.getenv("AZURE_OPENAI_FAST_DEPLOYMENT", "DeepSeek-V4-Flash")
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT")

    # --- GEMINI EMBEDDINGS (Fallback/Old) ---
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # --- VECTOR DB (QDRANT) ---
    QDRANT_URL = os.getenv("QDRANT_CLUSTER_ENDPOINT")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
    QDRANT_COLLECTION = "enterprise_rag"

    # --- REASONING ENGINE (GROQ) ---
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = "qwen/qwen3.6-27b"
    GROQ_FALLBACK_API_KEY = os.getenv("GROQ_FALLBACK_API_KEY")
    
    # --- PORTKEY GATEWAY ---
    PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY")
    PORTKEY_AZURE_VIRTUAL_KEY = os.getenv("PORTKEY_AZURE_VIRTUAL_KEY")
    PORTKEY_GROQ_VIRTUAL_KEY = os.getenv("PORTKEY_GROQ_VIRTUAL_KEY")
    
    # --- RERANKING ---
    JINA_API_KEY = os.getenv("JINA_API_KEY")
    
    # --- POSTGRES STATE PERSISTENCE ---
    NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL")


settings = Settings()