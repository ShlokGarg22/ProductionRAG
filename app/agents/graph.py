from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from app.config import settings
from app.agents.state import AgentState
from app.agents.nodes.planner import planner_node
from app.agents.nodes.retriever import retrieve_node
from app.agents.nodes.responder import generate_node

# 1. Initialize the State Graph
workflow = StateGraph(AgentState)

# 2. Define the Nodes
workflow.add_node("planner", planner_node)
workflow.add_node("retriever", retrieve_node)
workflow.add_node("responder", generate_node)

# 3. Define the Edges & Routing Logic
def route_planner(state: AgentState):
    """
    Routes the workflow based on the planner's decision.
    """
    if state["current_query"] == "CONVERSATIONAL":
        return "responder"
    return "retriever"

workflow.set_entry_point("planner")

# Conditional Edge: Planner -> Router -> (Retriever OR Responder)
workflow.add_conditional_edges(
    "planner",
    route_planner,
    {
        "retriever": "retriever",
        "responder": "responder"
    }
)

workflow.add_edge("retriever", "responder")
workflow.add_edge("responder", END)

# --- MEMORY UPGRADE ---
# MemorySaver allows the agent to remember conversations based on 'thread_id'
# We have upgraded to a Postgres checkpointer.
# For Neon serverless, set min_size=0, max_idle=0 to avoid stale SSL connections closing unexpectedly.
pool = ConnectionPool(
    conninfo=settings.NEON_DATABASE_URL, 
    kwargs={"autocommit": True},
    min_size=0,
    max_size=5,
    max_idle=0,
    max_lifetime=300
)
checkpointer = PostgresSaver(pool)
checkpointer.setup()

# 4. Compile the Graph with Memory
rag_agent = workflow.compile(checkpointer=checkpointer)
