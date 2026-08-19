import requests
import time

def run_query(query_type, query_text):
    print(f"\n[{query_type}] Query: '{query_text}'")
    t0 = time.time()
    
    try:
        r = requests.post(
            'http://127.0.0.1:8000/query_stream', 
            json={'q': query_text}, 
            stream=True
        )
        
        response_text = ""
        ttft = None
        for chunk in r.iter_content(chunk_size=None):
            if chunk:
                if ttft is None and b'"type": "token"' in chunk:
                    ttft = time.time() - t0
                
                # Parse basic text (simple decode for testing)
                try:
                    text_chunk = chunk.decode('utf-8')
                    if "content" in text_chunk:
                        # Just grab some text for the log
                        parts = text_chunk.split('"content": "')
                        if len(parts) > 1:
                            val = parts[1].split('"')[0]
                            response_text += val
                except:
                    pass
                    
        total = time.time() - t0
        
        if ttft:
            print(f"  -> TTFT: {ttft:.2f}s | Total Time: {total:.2f}s")
        else:
            print(f"  -> Total Time: {total:.2f}s (No tokens stream detected, likely blocked by Guardrails)")
            
    except Exception as e:
        print(f"Test failed: {e}")

def test_pipeline():
    print("Starting End-to-End Pipeline Tests...")
    
    # 1. NeMo Guardrails Test 1
    run_query("NeMo Test 1 (Off-topic)", "Can you bake a chocolate cake?")
    
    # 2. NeMo Guardrails Test 2
    run_query("NeMo Test 2 (Greeting)", "Hello bot, how are you?")
    
    # 3. Caching Test 1 (First Request)
    run_query("Cache Test 1 (Uncached)", "Explain Kubernetes ConfigMaps in detail.")
    
    # 4. Caching Test 2 (Exact Same Request)
    run_query("Cache Test 2 (Cached)", "Explain Kubernetes ConfigMaps in detail.")

if __name__ == "__main__":
    test_pipeline()
