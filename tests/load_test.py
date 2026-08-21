from locust import HttpUser, task, between
import json
import random

class RAGLoadTester(HttpUser):
    wait_time = between(1, 5)

    QUESTIONS = [
        "What is Kubernetes?",
        "How do I scale pods in Kubernetes?",
        "Explain what a Deployment is.",
        "How does Intel hardware accelerate AI?",
        "What are the benefits of vector databases?",
        "Tell me about the architecture of this RAG app."
    ]

    @task(1)
    def test_query_endpoint(self):
        question = random.choice(self.QUESTIONS)
        payload = {"q": question, "thread_id": "load_test_user"}
        headers = {'Content-Type': 'application/json'}
        
        with self.client.post("/query", data=json.dumps(payload), headers=headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(3)
    def test_health(self):
        self.client.get("/")
