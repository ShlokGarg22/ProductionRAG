import os
import sys
import types
import pandas as pd
from datasets import Dataset
from dotenv import load_dotenv

# --- RAGAS BUG FIX ---
# Ragas 0.4.3 tries to import ChatVertexAI from langchain_community, but it was removed in recent versions.
if 'langchain_community.chat_models.vertexai' not in sys.modules:
    # We create a fake module so the import doesn't crash the script.
    dummy_module = types.ModuleType('langchain_community.chat_models.vertexai')
    dummy_module.ChatVertexAI = type('ChatVertexAI', (object,), {})
    sys.modules['langchain_community.chat_models.vertexai'] = dummy_module
# ---------------------

# Ensure the app module can be found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env variables before importing modules that need them
load_dotenv()

from app.agents.graph import rag_agent
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

import openai.resources.chat.completions

original_async_create = openai.resources.chat.completions.AsyncCompletions.create
async def patched_async_create(self, *args, **kwargs):
    kwargs.pop("temperature", None)
    return await original_async_create(self, *args, **kwargs)
openai.resources.chat.completions.AsyncCompletions.create = patched_async_create

original_sync_create = openai.resources.chat.completions.Completions.create
def patched_sync_create(self, *args, **kwargs):
    kwargs.pop("temperature", None)
    return original_sync_create(self, *args, **kwargs)
openai.resources.chat.completions.Completions.create = patched_sync_create

from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision

# 1. Define Golden Dataset
# These are the questions we want to test, and the exact facts we expect the LLM to include.
test_cases = [
    {
        "question": "What is a CronJob?",
        "ground_truth": "A CronJob creates Jobs on a repeating schedule, similar to a line of a crontab file."
    },
    {
        "question": "What is the purpose of Horizontal Pod Autoscaling?",
        "ground_truth": "Horizontal Pod Autoscaling automatically updates a workload resource to scale the workload to match demand."
    }
]

def run_eval():
    print("Starting Ragas Evaluation Pipeline...\n")
    
    questions = []
    answers = []
    contexts = []
    ground_truths = []
    
    # 2. Run the agent to collect answers and contexts
    for idx, tc in enumerate(test_cases):
        q = tc["question"]
        print(f"[{idx+1}/{len(test_cases)}] Asking Agent: '{q}'")
        
        initial_state = {
            "messages": [{"role": "user", "content": q}],
            "current_query": q,
            "documents": [],
            "plan": ["Start Eval"],
            "status": "Running..."
        }
        
        # We use a unique thread_id per test so memory doesn't cross-contaminate
        config = {"configurable": {"thread_id": f"eval_thread_{idx}"}}
        
        final_output = rag_agent.invoke(initial_state, config=config)
        
        # Collect outputs
        answer = final_output.get("final_answer", "")
        retrieved_docs = final_output.get("documents", [])
        
        questions.append(q)
        answers.append(answer)
        contexts.append(retrieved_docs)
        ground_truths.append(tc["ground_truth"])
        
        print(f"  -> Generated Answer ({len(answer)} chars)")
        print(f"  -> Fetched {len(retrieved_docs)} context chunks\n")

    # 3. Format into a HuggingFace Dataset (required by Ragas)
    data = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths
    }
    dataset = Dataset.from_dict(data)
    
    # 4. Configure Ragas to use your existing Azure OpenAI deployments
    print("Initializing Azure OpenAI as Ragas Judge...")
    
    azure_llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
    )
    
    azure_embeddings = AzureOpenAIEmbeddings(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT")
    )

    ragas_llm = LangchainLLMWrapper(azure_llm)
    ragas_emb = LangchainEmbeddingsWrapper(azure_embeddings)

    metrics = [
        faithfulness,      # Checks if the answer hallucinates facts not in the context
        answer_relevancy,  # Checks if the answer directly addresses the question
        context_precision  # Checks if the retrieved context was highly relevant
    ]
    
    # 5. Execute Evaluation
    print("Executing mathematical grading... (This may take a minute)\n")
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=ragas_llm,
        embeddings=ragas_emb,
        raise_exceptions=False
    )
    
    # 6. Print the Results
    print("==================================================")
    print("RAGAS EVALUATION RESULTS")
    print("==================================================")
    
    df = result.to_pandas()
    # Format the dataframe for cleaner printing
    columns_to_show = ["question", "faithfulness", "answer_relevancy", "context_precision"]
    
    if df.empty or "question" not in df.columns:
        print("EVALUATION FAILED: Ragas returned an empty dataset. All LLM calls likely crashed.")
    else:
        # Only select columns that actually exist to avoid KeyErrors
        cols = [c for c in columns_to_show if c in df.columns]
        print(df[cols].to_string(index=False))
    
    print("\nOverall Results:")
    try:
        # In ragas 0.1.x, result is a dict with .items()
        for metric, score in result.items():
            print(f"- {metric}: {score:.4f}")
    except AttributeError:
        # In ragas 0.4.x, result is an EvaluationResult object
        print(result)

if __name__ == "__main__":
    run_eval()
