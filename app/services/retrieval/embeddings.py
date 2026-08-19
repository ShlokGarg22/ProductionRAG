import logfire
from langchain_openai import AzureOpenAIEmbeddings
from tenacity import retry, wait_exponential, stop_after_attempt
from app.config import settings

BATCH_SIZE = 50
_AZURE_DIM = 1536  # Default for text-embedding-3-small, update to 3072 if using large

_active_model = None

# ── Model initialisation ───────────────────────────────────────────────────────

def _init():
    """Initialise Azure OpenAI embedding model once per process."""
    global _active_model
    if _active_model is not None:
        return

    try:
        model = AzureOpenAIEmbeddings(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_deployment=settings.AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
        )
        model.embed_query("probe")
        logfire.info(f"Azure OpenAI embeddings ready (dim={_AZURE_DIM}).")
        _active_model = model
    except Exception as e:
        logfire.error(f"Failed to initialize Azure OpenAI embeddings: {e}")
        raise

# ── Public helpers ─────────────────────────────────────────────────────────────

def get_embedding_dim() -> int:
    """Return the vector dimension for the active model. Call after _init()."""
    return _AZURE_DIM

# ── Batch embedding with retry ─────────────────────────────────────────────────

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    reraise=True
)
def _embed_batch(batch: list[str]) -> list[list[float]]:
    try:
        return _active_model.embed_documents(batch)
    except Exception as e:
        err = str(e).lower()
        if any(x in err for x in ("429", "rate", "quota", "resource_exhausted", "too many requests")):
            logfire.warning(f"Azure OpenAI rate limit hit, retrying... Error: {e}")
            raise  # Let tenacity retry
        logfire.error(f"Azure OpenAI embedding failed irrecoverably: {e}")
        raise  # Do not retry on non-rate-limit errors (like Auth)

# ── Public API ─────────────────────────────────────────────────────────────────

def embed_query(query: str) -> list[float]:
    _init()
    return _active_model.embed_query(query)

def embed_texts(texts: list[str]) -> list[list[float]]:
    _init()
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        with logfire.span("Embed batch", model="azure", start=i, size=len(batch)):
            all_embeddings.extend(_embed_batch(batch))
    return all_embeddings