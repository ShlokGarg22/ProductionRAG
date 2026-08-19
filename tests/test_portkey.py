import requests
import time
import json

url = "http://localhost:8000/query"
headers = {"Content-Type": "application/json"}

print("Starting Portkey Gateway & Caching Test...\n")

# Test 1: First request (Cache Miss)
print("--- TEST 1: First Request (Expect Normal Latency) ---")
payload1 = {"q": "What is the capital of Japan? Just tell me the city name."}

start_time = time.time()
res1 = requests.post(url, headers=headers, json=payload1)
end_time = time.time()

print(f"Time Taken: {end_time - start_time:.2f} seconds")
if res1.status_code == 200:
    print(f"Response: {res1.json().get('answer')}")
else:
    print(f"Error: {res1.text}")


# Test 2: Identical request (Cache Hit)
print("\n--- TEST 2: Second Identical Request (Expect Instant Cache Hit via Portkey) ---")
payload2 = {"q": "What is the capital of Japan? Just tell me the city name."}

start_time = time.time()
res2 = requests.post(url, headers=headers, json=payload2)
end_time = time.time()

print(f"Time Taken: {end_time - start_time:.2f} seconds")
if res2.status_code == 200:
    print(f"Response: {res2.json().get('answer')}")
else:
    print(f"Error: {res2.text}")
    
print("\nTest Complete! If the second request was much faster, Portkey Semantic Caching is working.")
