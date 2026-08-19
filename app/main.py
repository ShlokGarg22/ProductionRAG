# ============================================================
# CRITICAL: logfire MUST be configured before ALL other imports
# so that spans from all modules are captured from the start.
# ============================================================
import logfire
import os
import sys
import asyncio
from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()
logfire.configure(token=os.getenv("LOGFIRE_TOKEN"))

# Now safe to import app modules - logfire is already active
from fastapi import FastAPI, Response
import json
from app.agents.graph import rag_agent
from app.guardrails.service import initialize_rails, guard
from app.services.cache import init_cache, check_semantic_cache, save_to_cache

from pydantic import BaseModel
from typing import Optional


# Initialize FastAPI
app = FastAPI(title="Enterprise Agentic RAG API")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logfire.instrument_fastapi(app)


@app.on_event("startup")
def startup_event():
    initialize_rails()
    init_cache()


class QueryRequest(BaseModel):
    q: str
    thread_id: Optional[str] = "default_user"
    
    
@app.get("/")
def home():
    return {"message": "Enterprise LangGraph RAG API is live."}


@app.get("/graph")
def get_graph_image():
    """
    Returns the Mermaid image of the agent's workflow.
    """
    try:
        png_bytes = rag_agent.get_graph().draw_mermaid_png()
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        return {"error": f"Could not generate graph image: {e}"}
    
    
@app.post("/query")
def query(request: QueryRequest):
    """
    Executes the LangGraph RAG flow with memory using a POST request.
    """
    q = request.q
    thread_id = request.thread_id

    initial_state = {
        "messages": [{"role": "user", "content": q}],
        "current_query": q,
        "plan": ["Start"],
        "status": "Initializing Graph..."
    }
    
    # Configuration for Memory (Thread ID)
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        with logfire.span("🚀 Processing Query", query=q, thread_id=thread_id):
            
            # 1. Input Gate: NeMo Guardrails Check
            rail_fired, warning_msg = guard(q)
            if rail_fired:
                return {
                    "question": q,
                    "answer": warning_msg,
                    "thought_process": ["Blocked by NeMo Guardrails"],
                    "status": "Blocked (Safety/Policy)",
                    "sources": []
                }
            
            # 2. Execution: LangGraph RAG pipeline
            # Run the graph synchronously to preserve Logfire context variables
            final_output = rag_agent.invoke(initial_state, config=config)
            
            final_answer = final_output.get("final_answer", "")
            documents = final_output.get("documents", [])
            plan = final_output.get("plan", [])
            status = final_output.get("status", "")
            
            return {
                "question": q,
                "answer": final_answer,
                "thought_process": plan,
                "status": status,
                "sources": documents
            }
    except Exception as e:
        logfire.error(f"❌ Backend Execution Failed: {e}")
        return {
            "question": q,
            "answer": "I apologize, but I encountered an internal error while processing your request. Please try again later.",
            "thought_process": ["Error encountered during execution."],
            "status": "error",
            "sources": []
        }

from fastapi.responses import StreamingResponse

@app.post("/query_stream")
def query_stream(request: QueryRequest):
    """
    Executes the LangGraph RAG flow and streams the result back via Server-Sent Events (SSE).
    Uses a fully synchronous streaming generator to avoid Windows ProactorEventLoop and NeMo Guardrails async conflicts.
    """
    q = request.q
    thread_id = request.thread_id

    initial_state = {
        "messages": [{"role": "user", "content": q}],
        "current_query": q,
        "plan": ["Start"],
        "status": "Initializing Graph..."
    }
    
    config = {"configurable": {"thread_id": thread_id}}
    
    def event_generator():
        # 1. Check Semantic Cache FIRST (Bypass Guardrails if it's a known safe query)
        cached_payload = check_semantic_cache(q)
        if cached_payload:
            if cached_payload.get("plan"):
                yield f"data: {json.dumps({'type': 'plan', 'content': cached_payload.get('plan')})}\n\n"
            if cached_payload.get("sources"):
                yield f"data: {json.dumps({'type': 'sources', 'content': cached_payload.get('sources')})}\n\n"
            if cached_payload.get("answer"):
                yield f"data: {json.dumps({'type': 'token', 'content': cached_payload.get('answer')})}\n\n"
            return
            
        # 2. Input Gate: NeMo Guardrails Check (Synchronous)
        rail_fired, warning_msg = guard(q)
        if rail_fired:
            yield f"data: {json.dumps({'type': 'error', 'content': warning_msg})}\n\n"
            return
            
        import queue
        import threading
        from langchain_core.callbacks.base import BaseCallbackHandler

        class StreamQueueCallback(BaseCallbackHandler):
            def __init__(self, q):
                self.q = q
            def on_llm_new_token(self, token: str, **kwargs):
                self.q.put(("token", token))
                
        stream_queue = queue.Queue()
        config["callbacks"] = [StreamQueueCallback(stream_queue)]
        
        def run_graph():
            try:
                with logfire.span("🚀 Streaming Query", query=q, thread_id=thread_id):
                    for stream_mode, data in rag_agent.stream(initial_state, config=config, stream_mode=["updates"]):
                        stream_queue.put(("updates", data))
            except Exception as e:
                logfire.error(f"❌ Streaming Backend Execution Failed: {e}")
                stream_queue.put(("error", "Internal Server Error occurred."))
            finally:
                stream_queue.put(("DONE", None))

        # Start graph execution in a background thread so it doesn't block the generator
        t = threading.Thread(target=run_graph)
        t.start()
        
        # Accumulators to build the cache payload
        acc_plan = []
        acc_sources = []
        acc_tokens = ""
        
        while True:
            msg_type, data = stream_queue.get()
            
            if msg_type == "DONE":
                # Save to cache on successful completion
                payload_dict = {
                    "plan": acc_plan,
                    "sources": acc_sources,
                    "answer": acc_tokens
                }
                save_to_cache(q, payload_dict)
                break
            elif msg_type == "error":
                yield f"data: {json.dumps({'type': 'error', 'content': data})}\n\n"
                break
            elif msg_type == "token":
                if data:
                    acc_tokens += data
                    yield f"data: {json.dumps({'type': 'token', 'content': data})}\n\n"
            elif msg_type == "updates":
                updates = data
                if "planner" in updates:
                    plan = updates["planner"].get("plan", [])
                    acc_plan = plan
                    yield f"data: {json.dumps({'type': 'plan', 'content': plan})}\n\n"
                elif "retriever" in updates:
                    docs = updates["retriever"].get("documents", [])
                    acc_sources = docs
                    yield f"data: {json.dumps({'type': 'sources', 'content': docs})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")