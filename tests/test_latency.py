import requests
import time

def test_latency():
    print('Starting latency test...')
    t0 = time.time()
    ttft = None
    
    try:
        r = requests.post(
            'http://127.0.0.1:8000/query_stream', 
            json={'q': 'What is the role of a LoadBalancer in Kubernetes?'}, 
            stream=True
        )
        
        for chunk in r.iter_content(chunk_size=None):
            if chunk:
                if ttft is None and b'"type": "token"' in chunk:
                    ttft = time.time() - t0
                    print(f'Time To First Token (TTFT): {ttft:.2f} seconds')
                    
        total = time.time() - t0
        print(f'Total Generation Time: {total:.2f} seconds')
        
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    test_latency()
