# Skill: open-movie-saas

## OPEN MOVIE SaaS Service Layer

This skill implements the **service/API layer** for OPEN MOVIE — turning the video generation pipeline into a multi-tenant SaaS with billing, job queue, user management, and API access.

## When to Use

- Ready to monetize the pipeline
- Need multi-user, multi-project support
- Want to expose as API for integrators
- Building a video generation platform

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      OPEN MOVIE SAAS                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  API GW  │──▶│  Auth    │──▶│  Rate    │──▶│  Router  │        │
│  │ (FastAPI)│   │ (JWT)    │   │  Limit   │   │          │        │
│  └──────────┘  └──────────┘  └──────────┘  └────┬─────┘        │
│                                                  │               │
│         ┌────────────────────────────────────────┼────────┐     │
│         ▼                                        ▼        ▼     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Projects   │  │   Jobs      │  │      Billing            │  │
│  │  Service    │  │  Queue      │  │  (Stripe/Paddle)        │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         │                │                      │                │
│         ▼                ▼                      ▼                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    WORKER POOL                            │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │   │
│  │  │ ASCII   │ │ AI Vid  │ │ Hybrid  │ │ Custom  │         │   │
│  │  │ Worker  │ │ Worker  │ │ Worker  │ │ Worker  │         │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘         │   │
│  └──────────────────────────────────────────────────────────┘   │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      STORAGE                               │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │   │
│  │  │ Postgres│ │  Redis  │ │   S3    │ │  CDN    │         │   │
│  │  │ (Meta)  │ │ (Queue) │ │(Assets) │ │(Delivery)│        │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘         │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Core Models

```python
# models.py
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import uuid

class ProjectStatus(Enum):
    DRAFT = "draft"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"

class JobStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class BackendType(Enum):
    ASCII = "ascii"
    AI_VIDEO = "ai_video"
    HYBRID = "hybrid"
    AUTO = "auto"

@dataclass
class User:
    id: str
    email: str
    name: str
    plan: str  # free, pro, team, enterprise
    credits: int  # Render credits
    created_at: datetime
    stripe_customer_id: Optional[str] = None

@dataclass
class Project:
    id: str
    user_id: str
    name: str
    brief: dict  # Project brief (YAML/JSON)
    status: ProjectStatus
    backend: BackendType
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    output_url: Optional[str] = None
    metadata: dict = None

@dataclass
class RenderJob:
    id: str
    project_id: str
    user_id: str
    status: JobStatus
    priority: int  # 0=low, 1=normal, 2=high, 3=urgent
    backend: BackendType
    progress: float  # 0.0-1.0
    current_frame: int
    total_frames: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]
    output_path: Optional[str]
    logs: List[str]
    cost_estimate: float
    actual_cost: float
```

## API Endpoints

```python
# api/routes.py
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel

app = FastAPI(title="OPEN MOVIE API", version="1.0.0")

# Auth dependency
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    ...

# Project endpoints
@app.post("/api/v1/projects")
async def create_project(
    project: ProjectCreate,
    user: User = Depends(get_current_user)
):
    """Create a new video project"""
    ...

@app.get("/api/v1/projects")
async def list_projects(
    user: User = Depends(get_current_user),
    status: Optional[ProjectStatus] = None,
    limit: int = 20,
    offset: int = 0
):
    """List user's projects"""
    ...

@app.get("/api/v1/projects/{project_id}")
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user)
):
    """Get project details"""
    ...

@app.patch("/api/v1/projects/{project_id}")
async def update_project(
    project_id: str,
    updates: ProjectUpdate,
    user: User = Depends(get_current_user)
):
    """Update project brief or settings"""
    ...

@app.delete("/api/v1/projects/{project_id}")
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user)
):
    """Archive/delete project"""
    ...

# Job endpoints
@app.post("/api/v1/projects/{project_id}/render")
async def start_render(
    project_id: str,
    render_request: RenderRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user)
):
    """Start a render job"""
    # Validate project ownership
    # Check credits
    # Estimate cost
    # Queue job
    # Deduct credits (reserved)
    return {"job_id": job.id, "status": "queued"}

@app.get("/api/v1/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    user: User = Depends(get_current_user)
):
    """Get real-time job status with progress"""
    ...

@app.get("/api/v1/jobs/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    user: User = Depends(get_current_user),
    tail: int = 100
):
    """Get job logs (streaming)"""
    ...

@app.post("/api/v1/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    user: User = Depends(get_current_user)
):
    """Cancel a running/queued job"""
    ...

# Output endpoints
@app.get("/api/v1/projects/{project_id}/download")
async def download_output(
    project_id: str,
    user: User = Depends(get_current_user)
):
    """Get signed download URL for completed video"""
    ...

@app.get("/api/v1/projects/{project_id}/preview")
async def get_preview(
    project_id: str,
    user: User = Depends(get_current_user)
):
    """Get preview (low-res, watermarked)"""
    ...

# Webhooks
@app.post("/api/v1/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe events"""
    ...

@app.post("/api/v1/webhooks/job-complete")
async def job_complete_webhook(payload: JobCompletePayload):
    """Internal webhook from workers"""
    ...
```

## Job Queue (Redis + BullMQ)

```python
# queue/manager.py
import redis.asyncio as redis
from bullmq import Queue, Worker, Job

class JobQueue:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.render_queue = Queue("renders", connection=self.redis)
        self.priority_queue = Queue("renders:priority", connection=self.redis)
    
    async def enqueue(self, job: RenderJob) -> str:
        queue = self.priority_queue if job.priority >= 2 else self.render_queue
        await queue.add("render", {
            "job_id": job.id,
            "project_id": job.project_id,
            "brief": job.brief,
            "backend": job.backend.value
        }, priority=job.priority)
        return job.id
    
    async def get_status(self, job_id: str) -> JobStatus:
        job = await Job.fromId(self.redis, job_id)
        return job.status if job else None
    
    async def cancel(self, job_id: str) -> bool:
        job = await Job.fromId(self.redis, job_id)
        if job:
            await job.remove()
            return True
        return False

# Worker process
async def render_worker(job: Job):
    job_data = job.data
    job_id = job_data["job_id"]
    
    try:
        # Update status
        await update_job_status(job_id, JobStatus.RUNNING)
        
        # Select backend
        backend = get_backend(job_data["backend"])
        
        # Progress callback
        async def progress_cb(frame: int, total: int):
            await update_job_progress(job_id, frame, total)
            await job.updateProgress(frame / total * 100)
        
        # Render
        output_path = await backend.render_full(
            brief=job_data["brief"],
            progress_callback=progress_cb
        )
        
        # Upload to CDN
        cdn_url = await upload_to_cdn(output_path, job_id)
        
        # Complete
        await complete_job(job_id, cdn_url, actual_cost)
        
    except Exception as e:
        await fail_job(job_id, str(e))
        raise
```

## Billing & Credits

```python
# billing/manager.py
import stripe
from dataclasses import dataclass

@dataclass
class Plan:
    id: str
    name: str
    monthly_price: int  # cents
    monthly_credits: int
    max_concurrent_jobs: int
    max_duration: int  # seconds
    backends: List[BackendType]
    priority_support: bool
    api_access: bool

PLANS = {
    "free": Plan(
        id="free", name="Free",
        monthly_price=0, monthly_credits=100,
        max_concurrent_jobs=1, max_duration=30,
        backends=[BackendType.ASCII],
        priority_support=False, api_access=False
    ),
    "pro": Plan(
        id="pro", name="Pro",
        monthly_price=2900, monthly_credits=5000,
        max_concurrent_jobs=3, max_duration=300,
        backends=[BackendType.ASCII, BackendType.AI_VIDEO],
        priority_support=False, api_access=True
    ),
    "team": Plan(
        id="team", name="Team",
        monthly_price=9900, monthly_credits=25000,
        max_concurrent_jobs=10, max_duration=600,
        backends=[BackendType.ASCII, BackendType.AI_VIDEO, BackendType.HYBRID],
        priority_support=True, api_access=True
    ),
    "enterprise": Plan(
        id="enterprise", name="Enterprise",
        monthly_price=0, monthly_credits=100000,  # Custom
        max_concurrent_jobs=50, max_duration=3600,
        backends=list(BackendType),
        priority_support=True, api_access=True
    ),
}

class BillingManager:
    def __init__(self, stripe_key: str):
        stripe.api_key = stripe_key
    
    async def check_credits(self, user: User, estimated_cost: float) -> bool:
        return user.credits >= estimated_cost
    
    async def reserve_credits(self, user: User, amount: float):
        user.credits -= amount
        await user.save()
        # Create credit transaction record
    
    async def refund_credits(self, user: User, amount: float):
        user.credits += amount
        await user.save()
    
    async def charge_overage(self, user: User, amount: float):
        # Charge via Stripe for overage
        pass
    
    def estimate_cost(self, brief: dict, backend: BackendType) -> float:
        """Estimate render cost in credits"""
        duration = brief.get("duration", 60)
        resolution = brief.get("resolution", "1080x1920")
        
        base_cost = {
            BackendType.ASCII: 0.1,      # credits/second
            BackendType.AI_VIDEO: 1.0,   # credits/second
            BackendType.HYBRID: 0.5,     # credits/second
        }
        
        resolution_multiplier = {
            "1080x1920": 1.0,
            "1920x1080": 1.0,
            "1280x720": 0.5,
            "3840x2160": 4.0,
        }
        
        return duration * base_cost.get(backend, 0.5) * \
               resolution_multiplier.get(resolution, 1.0)
```

## Worker Scaling

```python
# workers/scaler.py
class WorkerScaler:
    """Autoscale workers based on queue depth"""
    
    def __init__(self, k8s_client=None, docker_client=None):
        self.k8s = k8s_client
        self.docker = docker_client
    
    async def scale(self):
        queue_depth = await self._get_queue_depth()
        running_workers = await self._get_running_workers()
        
        # Target: 1 worker per 3 jobs, min 1, max 20
        target = max(1, min(20, queue_depth // 3 + 1))
        
        if target > running_workers:
            await self._scale_up(target - running_workers)
        elif target < running_workers:
            await self._scale_down(running_workers - target)
    
    async def _scale_up(self, count: int):
        for _ in range(count):
            # Launch worker pod/container
            await self.k8s.create_namespaced_pod(...)
```

## Configuration

```yaml
# saas-config.yaml
api:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  cors_origins: ["https://app.openmovie.io"]
  
database:
  url: "postgresql://user:pass@localhost/openmovie"
  pool_size: 20
  max_overflow: 10
  
redis:
  url: "redis://localhost:6379/0"
  
storage:
  s3_bucket: "openmovie-assets"
  s3_region: "us-east-1"
  cdn_domain: "cdn.openmovie.io"
  
auth:
  jwt_secret: "${JWT_SECRET}"
  jwt_algorithm: "HS256"
  access_token_expire: 3600  # 1 hour
  refresh_token_expire: 604800  # 7 days
  
billing:
  stripe_secret_key: "${STRIPE_SECRET_KEY}"
  stripe_webhook_secret: "${STRIPE_WEBHOOK_SECRET}"
  paddle_vendor_id: "${PADDLE_VENDOR_ID}"
  
workers:
  ascii:
    replicas: 2
    resources: {cpu: "2", memory: "4Gi", gpu: "1"}
  ai_video:
    replicas: 1
    resources: {cpu: "4", memory: "8Gi"}
  hybrid:
    replicas: 1
    resources: {cpu: "4", memory: "8Gi", gpu: "1"}
  
monitoring:
  prometheus_port: 9090
  sentry_dsn: "${SENTRY_DSN}"
  log_level: "INFO"
```

## Database Schema (PostgreSQL)

```sql
-- migrations/001_initial.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    plan VARCHAR(50) DEFAULT 'free',
    credits INTEGER DEFAULT 100,
    stripe_customer_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    brief JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'draft',
    backend VARCHAR(50) DEFAULT 'auto',
    output_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_status ON projects(status);

CREATE TABLE render_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    priority INTEGER DEFAULT 1,
    backend VARCHAR(50) NOT NULL,
    progress FLOAT DEFAULT 0.0,
    current_frame INTEGER DEFAULT 0,
    total_frames INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error TEXT,
    output_path TEXT,
    logs JSONB DEFAULT '[]',
    cost_estimate FLOAT DEFAULT 0.0,
    actual_cost FLOAT DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_jobs_project_id ON render_jobs(project_id);
CREATE INDEX idx_jobs_user_id ON render_jobs(user_id);
CREATE INDEX idx_jobs_status ON render_jobs(status);

CREATE TABLE credit_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,  -- positive = credit, negative = debit
    type VARCHAR(50) NOT NULL,  -- purchase, render, refund, bonus
    reference_id UUID,  -- job_id or invoice_id
    description TEXT,
    balance_after INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_transactions_user_id ON credit_transactions(user_id);
```

## Deployment (Docker Compose)

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: ./api
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://postgres:pass@db:5432/openmovie
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET=${JWT_SECRET}
      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
    depends_on: [db, redis]
    deploy:
      replicas: 3
  
  worker-ascii:
    build: ./workers/ascii
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CONFIG_PATH=/config/ascii-config.yaml
    volumes:
      - ./config:/config
      - ./outputs:/outputs
    deploy:
      replicas: 2
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
  
  worker-ai-video:
    build: ./workers/ai-video
    environment:
      - REDIS_URL=redis://redis:6379/0
      - HYPER_API_KEY=${HYPER_API_KEY}
    deploy:
      replicas: 1
  
  worker-hybrid:
    build: ./workers/hybrid
    environment:
      - REDIS_URL=redis://redis:6379/0
    deploy:
      replicas: 1
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
  
  db:
    image: postgres:16
    environment:
      - POSTGRES_DB=openmovie
      - POSTGRES_PASSWORD=pass
    volumes: [pgdata:/var/lib/postgresql/data]
    ports: ["5432:5432"]
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: [redisdata:/data]

volumes:
  pgdata:
  redisdata:
```

## File Structure

```
skills/open-movie-saas/
├── SKILL.md
├── api/
│   ├── main.py
│   ├── routes/
│   │   ├── projects.py
│   │   ├── jobs.py
│   │   ├── billing.py
│   │   └── webhooks.py
│   ├── auth.py
│   └── dependencies.py
├── models/
│   ├── __init__.py
│   ├── user.py
│   ├── project.py
│   └── job.py
├── queue/
│   ├── manager.py
│   └── workers/
│       ├── ascii_worker.py
│       ├── ai_video_worker.py
│       └── hybrid_worker.py
├── billing/
│   ├── manager.py
│   ├── plans.py
│   └── stripe_client.py
├── storage/
│   ├── s3_client.py
│   └── cdn.py
├── config/
│   └── saas-config.yaml
├── migrations/
│   └── 001_initial.sql
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.worker-ascii
│   ├── Dockerfile.worker-ai
│   └── docker-compose.yml
├── tests/
│   ├── test_api.py
│   ├── test_billing.py
│   └── test_queue.py
└── k8s/
    ├── deployment.yaml
    ├── service.yaml
    ├── hpa.yaml
    └── ingress.yaml
```

## API Client (for integrators)

```python
# sdk/python/openmovie.py
class OpenMovieClient:
    def __init__(self, api_key: str, base_url: str = "https://api.openmovie.io"):
        self.api_key = api_key
        self.base_url = base_url
    
    def create_project(self, name: str, brief: dict) -> Project:
        ...
    
    def start_render(self, project_id: str, backend: str = "auto") -> Job:
        ...
    
    def wait_for_completion(self, job_id: str, timeout: int = 3600) -> str:
        """Poll until done, return download URL"""
        ...
    
    def download(self, project_id: str, path: str):
        ...

# Usage
client = OpenMovieClient(api_key="om_...")
project = client.create_project("My Video", brief)
job = client.start_render(project.id, backend="hybrid")
url = client.wait_for_completion(job.id)
client.download(project.id, "./output.mp4")
```

---

*Service skill for OPEN MOVIE. Requires `open-movie-core` and all backend skills. Transforms pipeline into a production SaaS platform.*