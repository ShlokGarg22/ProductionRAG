# Enterprise Agentic RAG: Architecture & Engineering Decisions

This document is a comprehensive guide to everything we built in this project. It is designed to act as a reference sheet for your future projects, explaining not just *what* we did, but *why* we did it, what alternatives existed, and the engineering principles behind those choices.

---

## 1. What Are We Doing & How Are We Doing It?

We built a production-grade, Agentic RAG (Retrieval-Augmented Generation) system. Unlike a basic ChatGPT wrapper, this system is designed for enterprise speed, security, and scalability.

**The Tech Stack:**
- **Backend Framework:** FastAPI (Python) - High performance, native async support.
- **LLM Engine:** Azure OpenAI (`gpt-4o`) - Enterprise privacy and rate limits.
- **Vector Database:** Qdrant - Stores document embeddings for retrieval.
- **Caching Layer:** Redis Stack - Specifically used for *Semantic Caching*.
- **Security/Routing:** NVIDIA NeMo Guardrails - Intercepts prompts to block jailbreaks or off-topic queries before they hit the LLM.
- **Reranker:** Jina AI - Re-orders retrieved documents to put the most relevant context at the top.

---

## 2. Scalability of Our Architecture

Our architecture is highly scalable because it is **stateless at the application layer** and uses **serverless compute**.

- **Stateless FastAPI Containers:** Because our FastAPI backend doesn't save any data locally (it sends everything to Redis/Qdrant), we can spin up 1 container or 1,000 containers across the globe behind a Load Balancer, and they will all behave identically.
- **AWS ECS Fargate:** We are deploying using Fargate. Instead of paying for a fixed server (like an EC2 instance) that might sit idle or crash under heavy load, Fargate automatically provisions exactly the CPU and RAM needed for our containers. 
- **Decoupled Databases:** By keeping our Vector Database (Qdrant) and Cache (Redis) in separate containers (and eventually separate EFS volumes or managed services), a spike in LLM traffic won't crash our database, and vice versa.

---

## 3. Alternative Architectures (And Why We Didn't Choose Them)

Whenever you build a system, you have to weigh alternatives. Here is a breakdown of what we could have done, and why we chose our current path:

### A. Infrastructure: Fargate vs. EC2 vs. Lambda
- **Alternative (EC2):** We could have rented a standard virtual machine (EC2), installed Docker, and run it. 
  - *Why we rejected it:* Managing the underlying operating system, patching security vulnerabilities, and scaling up multiple VMs is painful.
- **Alternative (AWS Lambda):** Run the code entirely serverless per-request.
  - *Why we rejected it:* Lambda has "cold starts" which add latency. AI applications often require heavy libraries (like PyTorch and NeMo) which exceed Lambda's strict size limits.
- **Our Choice (ECS Fargate):** The perfect middle ground. It runs Docker containers indefinitely without us managing the OS, and it scales effortlessly.

### B. Storage: EFS vs. EBS vs. Managed Cloud Services
Because Fargate wipes its hard drive when it stops, we had to solve how to keep Redis and Qdrant data alive.
- **Alternative (Managed Services):** Use Pinecone for Vector DB and AWS ElastiCache for Redis.
  - *Why we rejected it:* You explicitly wanted to learn how to deploy and manage the open-source infrastructure yourself. Managed services abstract away the learning and can get expensive quickly.
- **Alternative (Amazon EBS):** Block storage attached to the container.
  - *Why we rejected it:* EBS volumes can only be attached to one container at a time in a specific Availability Zone.
- **Our Choice (Amazon EFS):** An elastic network file system. It can be mounted to multiple serverless Fargate containers simultaneously across different zones, ensuring our Redis and Qdrant data persists even if a container restarts.

### C. Caching: Exact String vs. Semantic Caching
- **Alternative (Exact String Match):** If a user asks "What is Kubernetes?", cache the answer. If they ask "Explain Kubernetes?", it triggers a full LLM generation because the string is technically different.
- **Our Choice (Redis Semantic Caching):** We used `RedisVL` to convert queries into vectors. If a user asks a question that is *conceptually similar* (e.g., 90% vector match) to a previously answered question, we instantly return the cached answer. This bypasses the heavy LLM call, dropping latency from ~15 seconds down to `0.4s`.

---

## 4. Key Engineering Decisions & Learnings

As you build more systems, you will encounter the same bottlenecks we solved in this project. Here are the crucial takeaways:

### 1. Defending Against Third-Party API Timeouts
**The Problem:** Our pipeline was taking over 80 seconds because the external `Jina AI` reranker API was occasionally hanging, completely blocking our Python code.
**The Fix:** We implemented a strict timeout (`timeout=5`) and a **graceful fallback**. If Jina doesn't respond in 5 seconds, we catch the exception and simply return the original (un-reranked) documents rather than crashing the system. 
**The Lesson:** *Never trust external APIs.* Always wrap network calls in timeouts and provide a fallback path.

### 2. Context Window Bloat (TTFT Optimization)
**The Problem:** Time To First Token (TTFT) was slow because we were feeding massive amounts of retrieved text into the Azure LLM prompt.
**The Fix:** We reduced `max_context_chars` in the responder node to strictly limit the token payload.
**The Lesson:** More context isn't always better. An LLM's speed degrades linearly with the amount of text you feed it. Always truncate context to the bare minimum required to answer the question.

### 3. Containerizing Heavy AI Libraries
**The Problem:** When we ran `docker-compose up`, the build took forever because NeMo Guardrails required PyTorch (a massive 500MB+ library), causing layer exports to drag.
**The Fix:** We structured our `Dockerfile` to leverage caching. By copying `requirements.txt` and running `pip install` *before* copying the rest of the application code (`COPY . .`), Docker caches the heavy PyTorch download. When we change our python code, Docker doesn't re-download PyTorch.
**The Lesson:** Always order your Dockerfile from "least likely to change" to "most likely to change" to maximize build cache efficiency.

### 4. Dependency Clashes in Linux vs. Windows
**The Problem:** Our LangGraph PostgreSQL checkpointing worked fine on Windows, but the Docker container crashed with `ImportError: no pq wrapper available`. 
**The Fix:** We explicitly installed `psycopg[binary]` and `libpq-dev` in the Linux container.
**The Lesson:** Python packages often rely on OS-level C-bindings. Just because it works on your local Windows machine doesn't mean it has the correct native binaries for an Ubuntu/Debian Docker container. Always test in Docker early.

---

Keep this document handy for your future architectural designs. When you build your next project, ask yourself:
1. Is my app stateless?
2. What happens if the third-party API I am using goes down?
3. Am I caching semantically or just exactly? 
4. Are my Docker layers optimized for caching?
