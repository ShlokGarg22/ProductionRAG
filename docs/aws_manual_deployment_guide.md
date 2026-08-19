# Comprehensive AWS Manual Deployment Guide

This guide is designed for absolute beginners. We are deploying an Enterprise Agentic RAG application using AWS ECS Fargate, EFS, and an Application Load Balancer. 

AWS has hundreds of settings. We will go through exactly what to click, what to name things, and crucially, *why* we are selecting that specific option.

---

## Phase 1: Uploading our Code to AWS ECR
*Concept: AWS cannot run a Docker container if it doesn't have the image file. ECR (Elastic Container Registry) is exactly like GitHub, but instead of holding source code, it securely holds your packaged Docker images.*

### Step 1.1: Create the Repository
1. Log in to the **AWS Management Console**.
2. In the top search bar, type `ECR` and click on **Elastic Container Registry**.
3. On the left sidebar, click **Repositories**.
4. Click the orange **Create repository** button.
5. **Visibility settings:** Select the **Private** radio button.
   - *Reasoning:* You do not want the public internet to be able to download your proprietary enterprise code.
6. **Repository name:** Type `krishnaik_rag_app`.
   - *Reasoning:* Naming it the exact same thing as your local Docker image prevents confusion later.
7. **Tag mutability:** Leave as **Mutable**.
   - *Reasoning:* This allows us to push a new version of the code and overwrite the `latest` tag easily.
8. **Image scan on push:** Toggle to **Enabled**.
   - *Reasoning:* AWS will automatically scan your Python packages for known security vulnerabilities every time you upload.
9. Scroll to the bottom and click **Create repository**.

### Step 1.2: Push your Local Image to AWS
1. Click on the name of your newly created repository (`krishnaik_rag_app`).
2. In the top right corner, click the **View push commands** button.
3. A popup will appear with 4 terminal commands. Open PowerShell/Terminal on your computer in your project folder.
4. **Command 1 (aws ecr get-login-password...):** Copy and paste it into your terminal, hit Enter.
   - *Reasoning:* This uses your AWS CLI credentials to get a temporary 12-hour password, logging your local Docker software into AWS so it has permission to upload.
5. **Command 2 (docker build...):** You can skip this if you already ran `docker build -t krishnaik_rag_app .` locally!
6. **Command 3 (docker tag...):** Copy and paste it, hit Enter.
   - *Reasoning:* This renames your local image to include the giant AWS URL (e.g., `12345.dkr.ecr.us-east-1.amazonaws.com/krishnaik_rag_app:latest`). Docker uses this URL to know exactly where to send the file.
7. **Command 4 (docker push...):** Copy and paste it, hit Enter.
   - *Reasoning:* This actually uploads the 3GB image to AWS. It will take a few minutes.

---

## Phase 2: Setting up Amazon EFS (Persistent Storage)
*Concept: Fargate destroys a container's hard drive whenever the container restarts. EFS is a permanent network-attached drive. We mount it to the containers so our Vector Embeddings and Caches survive restarts.*

### Step 2.1: Create the File System
1. In the AWS search bar, type `EFS` and click **EFS**.
2. Click the orange **Create file system** button.
3. **Name:** Type `RAG-Shared-Storage`.
4. **VPC:** Leave it as your `default` VPC.
   - *Reasoning:* The VPC is the Virtual Private Cloud (your isolated network). Everything must be in the same VPC so the services can see each other.
5. Click **Create**.

### Step 2.2: Create Access Points
*Concept: If Redis and Qdrant share the same hard drive, they might accidentally overwrite each other's files. An Access Point restricts a container to a specific sub-folder on the drive.*

1. Click the name of your new file system (`RAG-Shared-Storage`).
2. Click the **Access points** tab.
3. Click **Create access point**.
4. **Name:** Type `redis-data-point`.
5. **Root directory path:** Type `/redis`.
   - *Reasoning:* This tells EFS to create a hidden folder called `/redis` and trap the Redis container inside it.
6. **POSIX user:** 
   - **User ID:** Type `1000`.
   - **Group ID:** Type `1000`.
   - *Reasoning:* Docker containers run as specific Linux users (usually ID 1000). If we don't set this, the container will get a "Permission Denied" error when trying to save files.
7. **Root directory creation permissions:**
   - **Owner user ID:** Type `1000`.
   - **Owner group ID:** Type `1000`.
   - **Permissions:** Type `0777`.
   - *Reasoning:* `0777` grants full read/write/execute permissions to the folder so the container can create its database files.
8. Click **Create access point**.
9. **Repeat Steps 3-8** to create a second access point.
   - **Name:** `qdrant-data-point`
   - **Root directory path:** `/qdrant`
   - Use `1000` and `0777` just like before.

---

## Phase 3: The ECS Task Definition (The Blueprint)
*Concept: AWS ECS needs a blueprint that says: "Run these 3 containers together, give them 4GB of RAM, and attach the EFS drives." This blueprint is called a Task Definition.*

### Step 3.1: Create the Blueprint
1. In the AWS search bar, type `ECS` and click **Elastic Container Service**.
2. On the left sidebar, click **Task definitions**.
3. Click **Create new task definition**.
4. **Task definition family:** Type `enterprise-rag-blueprint`.
5. **Launch type:** Check the box for **AWS Fargate**.
   - *Reasoning:* Fargate means "Serverless." You don't have to manage EC2 instances.
6. **Operating system/Architecture:** Select **Linux/X86_64**.
7. **Task size:** 
   - **CPU:** Select `2 vCPU`.
   - **Memory:** Select `4 GB`.
   - *Reasoning:* AI frameworks (PyTorch, NeMo) are memory-hungry. 4GB ensures the container won't crash from Out-Of-Memory (OOM) errors.

### Step 3.2: Connect the EFS Volumes to the Blueprint
1. Scroll down to the **Storage** section and click **Add volume**.
2. **Volume name:** Type `redis-efs-volume`.
3. **Volume type:** Select **EFS**.
4. **File system ID:** Select your `RAG-Shared-Storage` file system.
5. **Access point ID:** Select the `redis-data-point`. Click **Add**.
6. **Repeat Steps 1-5** to add another volume:
   - **Volume name:** `qdrant-efs-volume`
   - **Access point:** `qdrant-data-point`.

### Step 3.3: Define the Containers
Scroll down to the **Container - 1** section. We will define 3 containers that will run side-by-side.

**Container 1 (The FastAPI Backend):**
1. **Name:** Type `api-backend`.
2. **Image URI:** Go to your ECR tab, copy the URI of your `krishnaik_rag_app:latest`, and paste it here.
3. **Port mappings:** 
   - **Container port:** Type `8000`.
   - **Protocol:** `TCP`.
   - *Reasoning:* Our FastAPI app runs on Uvicorn port 8000. This opens the port so the Load Balancer can send user questions to it.

**Container 2 (Redis Semantic Cache):**
1. Click **Add more containers**.
2. **Name:** Type `redis_cache`.
   - *CRITICAL REASONING:* Our Python code literally has the URL `redis://redis_cache:6379` hardcoded in `config.py`. AWS Service Discovery automatically routes the name `redis_cache` to this container. If you misspell this, the Python app will crash.
3. **Image URI:** Type `redis/redis-stack-server:latest`.
4. **Port mappings:** Delete the default port mapping.
   - *Reasoning:* The containers are running on the exact same Fargate host, so they can talk to each other without exposing ports to the outside world.
5. Under **Storage and Logging**, click **Add mount point**. 
   - **Source volume:** Select `redis-efs-volume`.
   - **Container path:** Type `/data`.
   - *Reasoning:* Redis saves its data inside `/data`. This intercepts anything Redis writes to `/data` and permanently saves it on the EFS drive.

**Container 3 (Qdrant Vector DB):**
1. Click **Add more containers**.
2. **Name:** Type `qdrant`.
   - *CRITICAL REASONING:* Our Python code uses the URL `http://qdrant:6333`. This name must be exact.
3. **Image URI:** Type `qdrant/qdrant:latest`.
4. Under **Storage and Logging**, click **Add mount point**.
   - **Source volume:** Select `qdrant-efs-volume`.
   - **Container path:** Type `/qdrant/storage`.
   - *Reasoning:* This is where Qdrant officially saves vector embeddings.

Scroll to the very bottom and click the orange **Create** button.

---

## Phase 4: Create the Application Load Balancer (ALB)
*Concept: We never want users talking directly to our containers. An ALB sits on the public internet, accepts HTTP traffic, and securely forwards it into our private AWS network.*

### Step 4.1: Create Security Groups (The Firewalls)
1. In the AWS search bar, type `VPC` and click it.
2. On the left sidebar under **Security**, click **Security Groups**.
3. Click **Create security group**.
4. **Security group name:** Type `ALB-Public-Firewall`.
5. **Description:** "Allows public internet to reach the Load Balancer."
6. **Inbound rules:** Click **Add rule**.
   - Type: `Custom TCP`
   - Port range: `8000` (or `80` if you want standard web traffic, but we are using 8000).
   - Source: `Anywhere-IPv4` (`0.0.0.0/0`).
7. Click **Create security group**.

### Step 4.2: Create the Load Balancer
1. In the AWS search bar, type `EC2` and click it.
2. On the left sidebar, scroll down to **Load Balancing** and click **Load Balancers**.
3. Click **Create load balancer**, choose **Application Load Balancer** (ALB), and click **Create**.
4. **Load balancer name:** Type `rag-public-alb`.
5. **Scheme:** Select **Internet-facing**.
6. **Network mapping:** Select your default VPC, and check *at least two* Availability Zone checkboxes below it. (AWS forces you to have at least two for redundancy).
7. **Security groups:** Click the `X` on the default one, and select `ALB-Public-Firewall` from the dropdown.
8. **Listeners and routing:**
   - **Protocol:** `HTTP` | **Port:** `8000`.
   - Under **Default action**, click the blue **Create target group** link. (This opens a new tab).

### Step 4.3: Create the Target Group
*Concept: The ALB needs to know exactly what it is throwing traffic at. The Target Group tracks the dynamic IP addresses of our Fargate containers.*
1. **Choose a target type:** Select **IP addresses**. (Crucial for Fargate).
2. **Target group name:** Type `rag-fargate-targets`.
3. **Protocol:** `HTTP` | **Port:** `8000`.
4. Click **Next**, then click **Create target group**. (You don't need to register targets manually; ECS does this automatically).
5. Go back to your Load Balancer tab, hit the refresh button next to the dropdown, and select `rag-fargate-targets`.
6. Scroll to the bottom and click **Create load balancer**.

---

## Phase 5: Launch the ECS Service!
*Concept: We have a Blueprint (Task Definition) and a Router (ALB). The ECS "Service" acts as the manager. It turns on the blueprint, attaches it to the router, and ensures it stays running 24/7.*

### Step 5.1: Create the Cluster
1. Go back to **ECS**.
2. On the left sidebar, click **Clusters**, then click **Create cluster**. 
3. **Cluster name:** Type `Enterprise-RAG-Cluster`. Leave defaults and click **Create**.

### Step 5.2: Create the Service Security Group
*Concept: Our containers need a firewall. We only want them accepting traffic from the Load Balancer, and we want them to have permission to talk to the EFS drive.*
1. Go back to **VPC -> Security Groups**. Click **Create security group**.
2. **Name:** Type `Fargate-Internal-Firewall`.
3. **Inbound Rule 1 (API Traffic):**
   - Type: `Custom TCP`
   - Port: `8000`
   - Source: Select the `ALB-Public-Firewall` security group from the dropdown. 
   - *Reasoning:* This is extremely secure. Hackers cannot reach port 8000; ONLY the Load Balancer is legally allowed to talk to the Fargate containers.
4. **Inbound Rule 2 (EFS Traffic):**
   - Type: `NFS` (Port automatically changes to `2049`).
   - Source: `Anywhere-IPv4`.
   - *Reasoning:* Fargate needs port 2049 open to mount the EFS network drive.
5. Click **Create security group**.

### Step 5.3: Deploy!
1. Go back to your `Enterprise-RAG-Cluster` in ECS.
2. In the **Services** tab at the bottom, click **Create**.
3. **Compute options:** Launch type -> **Fargate**.
4. **Deployment configuration:** 
   - Application type: **Service**.
   - Family: Select your `enterprise-rag-blueprint`.
   - Service name: Type `rag-live-service`.
   - Desired tasks: `1`. (This means 1 set of 3 containers).
5. Expand the **Networking** section.
   - **VPC:** Default.
   - **Security group:** Select your new `Fargate-Internal-Firewall`. (Remove the default one).
6. Expand the **Load balancing** section.
   - Load balancer type: **Application Load Balancer**.
   - Container to load balance: Select `api-backend:8000`.
   - Use existing load balancer -> Select `rag-public-alb`.
   - Target group -> Select `rag-fargate-targets`.
7. Click **Create**.

---

## Conclusion
You have just built an enterprise-grade cloud architecture by hand! 

Wait about 5 minutes for the Service status to say **"Running"**. 
To test your app, go to your **EC2 -> Load Balancers** page, copy the **DNS Name** (e.g., `rag-public-alb-12345.us-east-1.elb.amazonaws.com`), and paste it into your browser followed by `:8000/docs`.

You will see the FastAPI Swagger UI live on the public internet, backed by a highly secure, auto-healing, stateful Serverless architecture!
