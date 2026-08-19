import logfire
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.llm.providers import register_llm_provider
from nemoguardrails.llm import LLMModel, LLMResponse
from app.services.llm import get_llm, get_fast_llm

rails_app = None

class PortkeyLLMModel(LLMModel):
    def __init__(self):
        super().__init__()
        self.llm = get_fast_llm()

    async def generate_async(self, prompt, **kwargs) -> LLMResponse:
        # STUB: We only use NeMo for the 'check_if_off_topic' action!
        # By returning empty here, we prevent NeMo from wasting 25 seconds
        # trying to generate canonical dialog flows or full answers.
        return LLMResponse(content="")
        
    async def generate_events_async(self, *args, **kwargs):
        pass

def init_custom_llm(**kwargs):
    return PortkeyLLMModel()

async def check_if_off_topic(context: dict) -> bool:
    user_message = context.get("user_message", "")
    llm = get_fast_llm()
    prompt = f"Is the following input related to Kubernetes, Intel, or system architecture? Answer ONLY 'yes' or 'no'. Input: {user_message}"
    try:
        res = llm.invoke(prompt)
        content = res.content.strip().lower()
        # Ensure we only block if the LLM explicitly answers 'no' (or starts with 'no')
        return content.startswith("no")
    except Exception as e:
        logfire.error(f"check_if_off_topic failed: {e}")
        return True # Default to secure/off-topic if failure

def initialize_rails():
    global rails_app
    with logfire.span("Initializing NeMo Guardrails with Wrapped LLM and Custom Actions"):
        register_llm_provider("custom_llm", init_custom_llm)
        config = RailsConfig.from_path("app/guardrails/config")
        rails_app = LLMRails(config)
        rails_app.register_action(check_if_off_topic, name="check_if_off_topic")
        logfire.info("NeMo Guardrails initialized successfully.")

def guard(query: str) -> tuple[bool, str]:
    if not rails_app:
        logfire.warning("NeMo Guardrails not initialized. Bypassing.")
        return False, ""
        
    with logfire.span("🛡️ NeMo Guardrails Check", query=query):
        try:
            # NeMo generate method
            res = rails_app.generate(messages=[{"role": "user", "content": query}])
            
            if res and res.get("content"):
                content = res["content"]
                if "I am a specialized RAG assistant" in content:
                    logfire.info("NeMo Off-Topic Rail Fired.")
                    return True, content
                if "Hello! I am the Enterprise LangGraph" in content:
                    logfire.info("NeMo Greeting Rail Fired.")
                    return True, content
                    
            return False, ""
        except Exception as e:
            logfire.error(f"NeMo Check Failed: {e}")
            return False, ""
