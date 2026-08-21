from locust import HttpUser, task, between

class RAGLoadTester(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def test_health(self):
        self.client.get("/")
