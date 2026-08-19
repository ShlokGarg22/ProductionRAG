import requests
import time
import sys

def test_guardrail(query_type, query_text):
    print(f"\n==============================================")
    print(f"[{query_type}] Query: '{query_text}'")
    print(f"==============================================")
    t0 = time.time()
    
    try:
        r = requests.post(
            'http://127.0.0.1:8000/query_stream', 
            json={'q': query_text}, 
            stream=True
        )
        
        response_text = ""
        ttft = None
        print("Response: ", end="")
        for chunk in r.iter_content(chunk_size=None):
            if chunk:
                if ttft is None and b'"type": "token"' in chunk:
                    ttft = time.time() - t0
                
                try:
                    text_chunk = chunk.decode('utf-8')
                    if "content" in text_chunk:
                        parts = text_chunk.split('"content": "')
                        if len(parts) > 1:
                            val = parts[1].split('"')[0]
                            val = val.replace('\\n', '\n').replace('\\"', '"')
                            print(val, end="")
                            sys.stdout.flush()
                            response_text += val
                except:
                    pass
                    
        total = time.time() - t0
        
        print("\n")
        if "I am a specialized RAG assistant" in response_text or "Hello! I am the Enterprise LangGraph" in response_text or "Sorry, I cannot answer" in response_text:
            print(f"✅ BLOCKED BY GUARDRAILS (Time: {total:.2f}s)")
        elif ttft is None:
            print(f"✅ BLOCKED BY GUARDRAILS (Fast block, no tokens. Time: {total:.2f}s)")
        else:
            print(f"❌ PASSED GUARDRAILS (TTFT: {ttft:.2f}s, Total: {total:.2f}s)")
            
    except Exception as e:
        print(f"Test failed: {e}")

def run_tests():
    print("Testing NeMo Guardrails strictly...")
    
    # 1. Greeting Rail
    test_guardrail("Greeting", "Hello bot, how are you doing today?")
    
    # 2. General Off-Topic (not Kubernetes/Intel/Arch)
    test_guardrail("Off-Topic 1", "Can you give me a recipe for chocolate chip cookies?")
    
    # 3. General Off-Topic 2
    test_guardrail("Off-Topic 2", "Who won the superbowl last year?")
    
    # 4. On-Topic (Should pass)
    test_guardrail("On-Topic (Valid)", "What is a Kubernetes Pod?")

if __name__ == "__main__":
    run_tests()
