import logfire
from app.agents.state import AgentState
from app.services.llm import get_llm

from langchain_core.runnables import RunnableConfig

def generate_node(state: AgentState, config: RunnableConfig):
    """
    Synthesizes a response using both Documentation Context AND Conversation History.
    Uses the native Portkey client (not LangChain) so we can read the
    x-portkey-cache-status response header and surface Cache: Hit in the UI.
    """
    query = state["current_query"]

    history_str = ""
    for msg in state["messages"][:-1]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n"

    user_msg = state["messages"][-1]["content"] if state["messages"] else ""

    if query == "CONVERSATIONAL":
        logfire.info("Generating conversational response using memory.")
        prompt = f"""
        You are a friendly and helpful Enterprise AI Assistant.
        Answer the user's latest message using the CONVERSATION HISTORY below.

        CONVERSATION HISTORY:
        {history_str}

        LATEST MESSAGE:
        "{user_msg}"
        """
    else:
        logfire.info("Generating technical RAG response.")
        # Dramatically reduced from 25000 to prevent Azure OpenAI prefill throttling
        max_context_chars = 5000
        full_context = ""

        for doc in state["documents"]:
            doc_str = doc.get("page_content", "")
            if len(full_context) + len(doc_str) < max_context_chars:
                full_context += doc_str + "\n\n"
            else:
                logfire.warning("Context truncated to fit Groq TPM limits.")
                break

        prompt = f"""
        You are a Senior Technical Architect.
        Answer the question CONCISELY using the TECHNICAL CONTEXT provided.
        Keep your response extremely brief, direct, and to the point (under 3 short paragraphs).
        Use bullet points for readability. DO NOT write long essays.

        TECHNICAL CONTEXT:
        {full_context}

        CONVERSATION HISTORY:
        {history_str}

        USER QUESTION:
        "{user_msg}"
        """

    with logfire.span("✍️ LLM Synthesis"):
        try:
            llm = get_llm()
            # Pass the LangGraph config to the LLM so it can stream tokens back to the main SSE loop!
            res = llm.invoke(prompt, config=config)
            content = res.content
            
            logfire.info("✅ Response synthesised via LLM.")
            plan_update = state["plan"]
            status = "Response generated."

            return {
                "final_answer": content,
                "status": status,
                "plan": plan_update,
                "messages": [{"role": "assistant", "content": content}]
            }

        except Exception as e:
            logfire.error(f"LLM Generation failed: {e}")
            raise e