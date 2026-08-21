# 🏛️ Architectural Decision Record (ADR)

This document explains every major decision we made while building your Enterprise RAG application. It is broken down into **AI/Algorithmic Decisions** (what makes this RAG smarter than others) and **Infrastructure Decisions** (what makes it scalable and cheap).

---

## Part 1: AI & Algorithmic Decisions 
*(These are the decisions that made your RAG application state-of-the-art and mathematically superior to standard tutorials).*

### 1. Hybrid Search (Dense Vectors + BM25 Sparse Vectors)
* **What it does:** When searching Qdrant, we search using two different algorithms simultaneously and merge the results.
* **Why we chose it:** Dense Vectors (Azure) are amazing at understanding *meaning*. If you search "How do I reboot a server", it will find a document about "Restarting a node". However, Dense Vectors are terrible at exact matches (like searching for a specific serial number "Intel i9-14900K"). **BM25** is an old-school keyword search algorithm. By running both at the same time (Hybrid Search), we guarantee the system understands the *concept* of the user's question, but never misses exact *keywords*.
* **Could we do better?** This is the current gold standard for retrieval. 

### 2. Cross-Encoder Reranking (Jina AI)
* **What it does:** Takes the Top 10 results from Qdrant and scientifically re-sorts them based on actual relevance to the question.
* **Why we chose it:** Vector databases (like Qdrant) are lightning-fast, but they are "dumb". They only compare numbers (vectors). They don't actually *read* the text. A Cross-Encoder (Jina) is a heavy neural network that reads the User Question and the Document Chunk side-by-side to see if they logically match. It is too slow to run on a million documents, which is why we use Qdrant to narrow it down to 10, and then use Jina to pick the absolute perfect top 5.
* **Could we do better?** We could host our own Cross-Encoder model (like `bge-reranker-large`) locally on AWS to save API costs, but Jina AI's API is incredibly fast and cheap for a startup.

### 3. LLM Document Grading (The "Self-RAG" approach)
* **What it does:** Forces the LLM to read the Top 5 documents and vote "yes" or "no" on whether they actually contain the answer *before* writing the final response.
* **Why we chose it:** **This is how we completely eliminated hallucinations.** Even with Jina, sometimes the user asks a question that simply isn't in your PDFs. A normal RAG system would blindly send the best matches to the LLM and the LLM would try to guess. By adding this strict grading step in LangGraph, we throw out garbage documents. If all documents are thrown out, the system safely admits it doesn't know, rather than lying.

### 4. Text Chunking (1000 characters, 200 overlap)
* **What it does:** Splits massive PDFs into small paragraphs before vectorizing them.
* **Why we chose it:** 1,000 characters is roughly 1-2 paragraphs. This is the "Goldilocks zone" for LLMs—it's small enough that the math (embedding) perfectly captures the specific topic, but large enough that it actually contains useful information. The **200 character overlap** is crucial: it ensures that if a sentence is chopped in half at the end of Chunk A, the beginning of Chunk B contains the rest of the sentence plus the previous context!

---

## Part 2: Cloud & Infrastructure Decisions

### 5. The Compute: AWS Fargate (Instead of EC2 or Lambda)
* **Why we chose it:** Fargate is "Serverless Docker". Traditional EC2 servers require you to manually install security patches and fix crashed servers. AWS Lambda times out because LLM streaming takes too long. Fargate gives you the zero-maintenance of serverless, but the power of a dedicated server.
* **Could we do better?** If your company grows to have 500+ microservices, you would want to migrate to Kubernetes (AWS EKS). For your current scale, Fargate is the absolute best choice.

### 6. The Vector Database: Qdrant (Instead of Pinecone)
* **Why we chose it:** Qdrant is open-source, written in ultra-fast Rust, and natively supports the Hybrid Search we needed. Most importantly, we can run it completely for free inside your Fargate container by mounting it to an AWS EFS hard drive. 
* **Could we do better?** Pinecone (a fully managed cloud database) is easier to set up but *extremely expensive*. Running Qdrant yourself saves hundreds of dollars a month.

### 7. The Cost Saver: Redis Semantic Cache
* **Why we chose it:** LLM API calls are expensive and slow (15-40 seconds). By checking Redis first to see if anyone has asked a similar question recently, we cut response times down to **1 second** and cost down to **$0**.
* **Could we do better?** Right now, we rely on a math equation ("Cosine Distance") to see if two questions mean the same thing. In the future, we could add a tiny, ultra-fast local AI model to act as a "Judge" to verify if the cached answer is truly perfectly relevant.

### 8. The Manager: Portkey AI Gateway
* **Why we chose it:** If Azure OpenAI crashes or rate-limits you, Portkey automatically catches the error and instantly reroutes the request to Groq (Llama-3). It guarantees your app never goes down. It also gives you a beautiful dashboard to track exactly how much money each user is costing you.

### 9. The Security Guard: NeMo Guardrails
* **Why we chose it:** Nvidia NeMo is open-source and runs locally. It intercepts malicious prompts (jailbreaks) *before* they are sent to Azure, protecting your data and saving you API costs.

### 10. The Networking Hack: Next.js API Proxy
* **Why we chose it:** When we deployed, browsers blocked the connection because the frontend was HTTPS but the backend was HTTP. By having the Next.js server secretly pass the messages to the backend, we bypassed the browser's security block perfectly.
* **Could we do better?** Yes. The "true enterprise" way is to buy a Custom Domain Name (`krishnaik-rag.com`), generate an SSL Certificate, and attach it to your ALB. However, our proxy workaround allowed us to launch to production immediately for free!
