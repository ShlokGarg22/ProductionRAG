import json
import logfire
from langchain_openai import AzureChatOpenAI
from app.config import settings

def get_llm():
    """
    Returns the primary LLM, connecting DIRECTLY to Azure OpenAI to completely 
    bypass the Portkey Gateway latency bottlenecks.
    """
    gateway_llm = AzureChatOpenAI(
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_deployment=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
        model_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
        max_tokens=1024,
        streaming=True
    )
    return gateway_llm

def get_fast_llm():
    """
    Returns an ultra-fast LLM directly from Azure.
    Used exclusively for rapid decision-making tasks like Guardrails and Planner routing.
    """
    fast_llm = AzureChatOpenAI(
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_deployment=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
        model_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
        max_tokens=1024,
        streaming=False
    )
    return fast_llm
