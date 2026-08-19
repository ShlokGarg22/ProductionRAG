import requests
import time
import sys

def run_query(query_type, query_text):
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
                
                # Parse basic text (simple decode for testing)
                try:
                    text_chunk = chunk.decode('utf-8')
                    if "content" in text_chunk:
                        parts = text_chunk.split('"content": "')
                        if len(parts) > 1:
                            val = parts[1].split('"')[0]
                            # Handle simple escapes
                            val = val.replace('\\n', '\n').replace('\\"', '"')
                            print(val, end="")
                            sys.stdout.flush()
                            response_text += val
                except:
                    pass
                    
        total = time.time() - t0
        
        print("\n")
        if ttft:
            print(f"  -> TTFT (Time to First Token): {ttft:.2f}s | Total Time: {total:.2f}s")
        else:
            print(f"  -> Total Time: {total:.2f}s (No tokens stream detected)")
            
    except Exception as e:
        print(f"Test failed: {e}")

def test():
    # Brand new questions to bypass Redis Cache and hit the Azure LLM + Qdrant
    run_query("Docker Test 1 (Uncached)", "How do I implement a rolling update in Kubernetes?")
    
    run_query("Docker Test 2 (Uncached)", "What are the core differences between a Pod and a Node?")

if __name__ == "__main__":
    test()
