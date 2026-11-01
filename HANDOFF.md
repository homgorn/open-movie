# OPEN MOVIE — Handoff Document & Roadmap

> **Status**: Foundation complete. Core pipeline, 4 backends, 5 universal skills, CLI, sample project all working.
> **Next**: New project kickoff — extend video types, production hardening, SaaS launch.

---

## 1. Current State (as of 2026-11-02)

### ✅ Delivered

| Component | Location | Status |
|-----------|----------|--------|
| **Core Pipeline** | `src/open_movie_core/` | Complete |
| **ProjectBrief (YAML)** | `brief.py` | Complete — declarative, validated |
| **CLI (`om`)** | `cli.py` | Complete — init/validate/render/scene/audio/doctor/backends |
| **ASCII Backend** | `backends/ascii_backend.py` | Complete — Three.js + ASCII shader, Puppeteer→FFmpeg |
| **AI Video Backend** | `backends/ai_video_backend.py` | Complete — Hyper MCP (Veo/Seedance/Kling), scene chaining |
| **Hybrid Backend** | `backends/hybrid_backend.py` | Complete — Planner + Compositor + Temporal Stabilizer |
| **Audio Generator** | `audio/generator.py` | Complete — Procedural (score.py port) + AI stub |
| **FFmpeg Encoder** | `ffmpeg/encoder.py` | Complete — Async, frames+audio, progress callbacks |
| **5 Universal Skills** | `skills/open-movie-*/` | Complete — Core, ASCII, AI Video, Hybrid, SaaS |
| **Sample Project** | `project.yaml` | Complete — 148s LLM film, 7 scenes, hybrid backend |

### 🏗️ Architecture Snapshot

```
┌─────────────────────────────────────────────────────────────────┐
│                        OPEN MOVIE CORE                           │
├─────────────────────────────────────────────────────────────────┤
│  ProjectBrief (YAML) ──▶ Pipeline ──▶ Backend Registry          │
│                                        │                         │
│                    ┌───────────────────┼───────────────────┐    │
│                    ▼                   ▼                   ▼    │
│              ┌──────────┐        ┌────────────┐        ┌──────────┐
│              │  ASCII   │        │  AI Video  │        │  Hybrid  │
│              │ Backend  │        │  Backend   │        │ Backend  │
│              └──────────┘        └────────────┘        └──────────┘
│                    │                   │                   │    │
│                    └───────────────────┼───────────────────┘    │
│                                        ▼                         │
│                              ┌─────────────────┐                │
│                              │   Compositor    │                │
│                              │ (Hybrid only)   │                │
│                              └────────┬────────┘                │
│                                       ▼                          │
│                              ┌─────────────────┐                │
│                              │  Audio Generator│                │
│                              │ (Procedural/AI) │                │
│                              └────────┬────────┘                │
│                                       ▼                          │
│                              ┌─────────────────┐                │
│                              │  FFmpeg Encoder │                │
│                              └─────────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

### 🔑 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **YAML-first brief** | Human-readable, git-diffable, validated before render |
| **Backend registry** | Swap backends by changing one line (`backend: "hybrid"`) |
| **Frame-by-frame + full-render dual API** | ASCII needs frame control; AI/Hybrid work clip-based |
| **Procedural audio default** | Deterministic, zero-cost, EBU R128 compliant |
| **Skills as portable units** | Each backend = independent skill, composable for SaaS |
| **Deterministic ASCII** | Same brief + same seed = identical output (critical for regression) |

---

## 2. Roadmap — Phased Delivery

### Phase 0: Stabilization (Week 1-2) — **IMMEDIATE**

| Task | Owner | Effort | Acceptance |
|------|-------|--------|------------|
| Fix ASCII backend `render_full` integration | | 2d | `om render --backend ascii` works end-to-end |
| Connect real Hyper MCP to AI backend | | 1d | `om render --backend ai_video` generates real clips |
| Hybrid backend integration test | | 2d | All 7 scenes render with correct code/AI split |
| CI/CD pipeline (GitHub Actions) | | 1d | Lint, type-check, test on push |
| Type hints + mypy strict mode | | 1d | `mypy src/` passes |
| Unit test coverage >80% | | 2d | `pytest --cov=open_movie_core` |

**Deliverable**: `om render --brief project.yaml --backend hybrid --output test.mp4` produces valid 1080×1920 MP4 with audio.

---

### Phase 1: Video Type Expansion (Week 3-6)

> **Goal**: Support 10+ video types beyond "explainer/film"

#### 1.1 Video Type Registry System
```python
# New: src/open_movie_core/video_types/
# Each type = template + default brief + specialized pipeline
```

| Video Type | Template | Duration | Backend | Use Case |
|------------|----------|----------|---------|----------|
| **Explainer** | `explainer.yaml` | 60-180s | Hybrid | Technical tutorials, product demos |
| **Short/Reel** | `short.yaml` | 15-60s | AI Video | TikTok, Reels, Shorts |
| **Data Story** | `datastory.yaml` | 30-120s | ASCII | Dashboards, metrics, analytics |
| **Talking Head** | `talking_head.yaml` | 30-300s | AI Video | Avatar/clone, narration |
| **Product Demo** | `product_demo.yaml` | 60-180s | Hybrid | SaaS walkthroughs |
| **Music Visualizer** | `music_viz.yaml` | 180-300s | ASCII | Audio-reactive |
| **Course/Lesson** | `course.yaml` | 300-1800s | Hybrid | Educational content |
| **Ad Creative** | `ad_creative.yaml` | 15-30s | AI Video | Paid social ads |
| **Case Study** | `case_study.yaml` | 120-300s | Hybrid | B2B testimonials |
| **Documentary** | `documentary.yaml` | 300-1800s | Hybrid | Long-form narrative |

#### 1.2 Per-Type Specializations

```yaml
# explainer.yaml defaults
pipeline:
  backend: "hybrid"
  quality: "high"
scenes:
  - id: "hook"      # 0-5s: Problem statement
  - id: "context"   # 5-20s: Background
  - id: "solution"  # 20-80s: Main content (diagram + narration)
  - id: "demo"      # 80-140s: Live/code demo
  - id: "cta"       # 140-160s: Call to action
audio:
  style: "instructional"
  bpm: 72
  progression: ["C", "Am", "F", "G"]
```

#### 1.3 Template Generator
```bash
om init --type explainer --brief my_video.yaml
om init --type short --brief reel.yaml
```

**Deliverable**: `om init --type <type>` creates production-ready brief with scene structure, timing, and backend hints.

---

### Phase 2: Production Hardening (Week 7-10)

| Area | Tasks | Acceptance |
|------|-------|------------|
| **Reliability** | Retry logic, circuit breakers, dead letter queue | 99.9% job success |
| **Observability** | Structured logging, Prometheus metrics, Sentry tracing | Dashboards in Grafana |
| **Cost Control** | Per-job budget enforcement, cost estimation API | No surprise bills |
| **Security** | Secret scanning, signed URLs, rate limiting | SOC2-ready |
| **Performance** | Worker pooling, GPU sharing, frame caching | <$0.10/min render cost |
| **Quality Gates** | Visual regression (Playwright), audio loudness, metadata | Auto-block bad renders |

#### 2.1 Worker Architecture (Production)

```yaml
# docker-compose.prod.yml
services:
  worker-ascii:
    deploy:
      replicas: 3
      resources:
        reservations:
          devices: [{driver: nvidia, count: 1, capabilities: [gpu]}]
    environment:
      - MAX_CONCURRENT=2
      - CHROME_POOL_SIZE=4

  worker-ai-video:
    deploy:
      replicas: 2
    environment:
      - HYPER_API_KEY=${HYPER_API_KEY}
      - MAX_CONCURRENT=5

  worker-hybrid:
    deploy:
      replicas: 2
      resources:
        reservations:
          devices: [{driver: nvidia, count: 1, capabilities: [gpu]}]
```

#### 2.2 Queue & Scheduling

```python
# queue/scheduler.py
class JobScheduler:
    PRIORITY_WEIGHTS = {"urgent": 100, "high": 50, "normal": 10, "low": 1}
    
    async def schedule(self, job: RenderJob):
        # Fair-share per user + priority
        # GPU-aware placement (ASCII/Hybrid → GPU nodes)
        # Cost-aware: reject if user budget exceeded
```

---

### Phase 3: SaaS Launch (Week 11-16)

> **Goal**: Public beta with billing, multi-tenancy, API access

#### 3.1 API Surface (FastAPI)

```python
# api/routes.py — Public endpoints
POST   /api/v1/projects              # Create project
GET    /api/v1/projects              # List (paginated, filtered)
GET    /api/v1/projects/{id}         # Get details
PATCH  /api/v1/projects/{id}         # Update brief
DELETE /api/v1/projects/{id}         # Archive

POST   /api/v1/projects/{id}/render  # Start render job
GET    /api/v1/jobs/{job_id}         # Job status + progress (SSE)
GET    /api/v1/jobs/{job_id}/logs    # Streaming logs
POST   /api/v1/jobs/{job_id}/cancel  # Cancel

GET    /api/v1/projects/{id}/download # Signed URL (expires 1h)
GET    /api/v1/projects/{id}/preview  # Low-res watermarked preview

POST   /api/v1/webhooks/stripe       # Billing events
POST   /api/v1/webhooks/job-complete # Internal completion
```

#### 3.2 Billing & Plans

| Plan | $/mo | Credits/mo | Concurrent | Max Dur | Backends | API |
|------|------|------------|------------|---------|----------|-----|
| **Free** | $0 | 100 | 1 | 30s | ASCII | ❌ |
| **Creator** | $29 | 5,000 | 3 | 5min | ASCII, AI Video | ✅ |
| **Pro** | $99 | 25,000 | 10 | 10min | All | ✅ |
| **Team** | $299 | 100,000 | 25 | 30min | All + Custom | ✅ |
| **Enterprise** | Custom | Unlimited | 50+ | 60min | All + Dedicated | ✅ |

**Credit costs**: ASCII=0.1/s, AI Video=1.0/s, Hybrid=0.5/s (per output second)

#### 3.3 Python SDK (for integrators)

```python
# pip install openmovie
from openmovie import OpenMovieClient

client = OpenMovieClient(api_key="om_live_...")
project = client.create_project("My Explainer", type="explainer")
job = client.start_render(project.id, backend="hybrid")
url = client.wait_for_completion(job.id, timeout=1800)
client.download(project.id, "./output.mp4")
```

**Deliverable**: Public API at `api.openmovie.io` with docs, SDK, example apps.

---

### Phase 4: Platform Evolution (Month 5+)

| Initiative | Description |
|------------|-------------|
| **Marketplace** | Community templates, custom backends, model fine-tunes |
| **Real-time Collaboration** | Multi-user editing, live preview, comments |
| **Brand Kits** | Per-org colors, fonts, logos, intro/outro templates |
| **Analytics** | Viewer retention, drop-off points, A/B test variants |
| **Localization** | Auto-translate + dubbing (ElevenLabs), subtitle burn-in |
| **Mobile SDK** | React Native / Flutter components for in-app generation |
| **Enterprise SSO** | SAML/OIDC, SCIM provisioning, audit logs |

---

## 3. Technical Debt & Known Issues

| Issue | Severity | Location | Mitigation |
|-------|----------|----------|------------|
| ASCII `render_full` not wired to `render.js` | High | `ascii_backend.py:180` | Use frame-by-frame for now; fix in Phase 0 |
| AI backend uses mock Hyper calls | High | `ai_video_backend.py:_call_hyper` | Connect real MCP in Phase 0 |
| Hybrid compositor untested | Medium | `hybrid_backend.py:_composite_ai_frames` | Integration test in Phase 0 |
| No GPU memory management | Medium | Workers can OOM | Add `nvidia-smi` monitoring, worker restart |
| Audio loudnorm via ffmpeg subprocess | Low | `generator.py:_apply_loudnorm` | Replace with `pyloudnorm` for speed |
| No brief versioning | Low | `brief.py` | Add `version` field, migration scripts |
| Single-threaded frame rendering | Medium | `pipeline.py:_render_frame_by_frame` | ThreadPoolExecutor works but no GPU batching |

---

## 4. Next Project Kickoff Checklist

### 4.1 New Project Setup (5 minutes)

```bash
# 1. Clone / copy OPEN MOVIE
cp -r H:\OPEN MOVIE H:\MY_NEW_PROJECT
cd H:\MY_NEW_PROJECT

# 2. Activate skills (if using opencode)
# opencode skill-fit --project .

# 3. Create project brief from template
om init --type explainer --brief project.yaml

# 4. Edit project.yaml with your content
# - Update project.id, title, duration
# - Modify scenes: id, start, end, description, parameters
# - Adjust audio style/progression if needed

# 5. Validate
om validate --brief project.yaml

# 6. Test render (fast ASCII first)
om render --brief project.yaml --backend ascii --output test.mp4

# 7. Full quality render
om render --brief project.yaml --backend hybrid --output final.mp4
```

### 4.2 Custom Video Type Creation

```bash
# 1. Add template
cp skills/open-movie-core/templates/explainer.yaml \
   skills/open-movie-core/templates/my_custom_type.yaml

# 2. Edit template with your scene structure
# 3. Register in CLI (cli.py: cmd_init)
# 4. Test: om init --type my_custom_type --brief test.yaml
```

### 4.3 Custom Backend Development

```python
# 1. Create backend class
# src/open_movie_core/backends/my_backend.py
from .base import VideoBackend, BackendCapabilities, register_backend

@register_backend("my_backend")
class MyBackend(VideoBackend):
    def get_capabilities(self): ...
    def render_frame(self, scene, t, frame_idx): ...
    async def render_full(self, brief, progress_callback): ...

# 2. Add config to pipeline
# project.yaml:
# pipeline:
#   backend: "my_backend"
#   backend_config:
#     my_backend: { ... }
```

---

## 5. Video Type Extension Guide

### 5.1 Adding a New Video Type

1. **Create template** in `skills/open-movie-core/templates/{type}.yaml`
2. **Define scene archetypes** (hook, context, demo, cta, etc.)
3. **Set default backend** based on visual needs
4. **Add audio profile** (style, BPM, progression)
5. **Register in CLI** (`cmd_init` type choices)
6. **Add to SDK** (`openmovie/types.py`)

### 5.2 Scene Archetype Library

| Archetype | Duration | Visual | Audio Cue | Backend Hint |
|-----------|----------|--------|-----------|--------------|
| `hook` | 3-5s | Bold text + motion | Impact sound | AI Video |
| `problem` | 10-20s | Relatable scenario | Tension chord | Hybrid |
| `solution` | 20-60s | Diagram + narration | Stable progression | ASCII/Hybrid |
| `demo` | 30-120s | Screen recording + overlay | Click sounds | ASCII |
| `proof` | 15-30s | Metrics, testimonials | Confidence chord | AI Video |
| `cta` | 5-10s | Button + text | Resolve chord | Hybrid |
| `transition` | 2-5s | Morph/wipe | Whoosh | AI Video |

### 5.3 Parameterizing Scenes

```yaml
# In project.yaml scene.parameters
- id: "demo"
  parameters:
    # Code-rendered elements
    code_elements:
      - type: "terminal"
        command: "npm run build"
        output: "Build successful ✓"
      - type: "code_diff"
        before: "const x = 1"
        after: "const x = 2"
    # AI-rendered elements  
    ai_elements:
      - type: "screen_recording"
        prompt: "Developer typing in VS Code, close-up hands"
        model: "veo-3.1"
      - type: "ui_overlay"
        prompt: "Floating hologram showing build logs"
        model: "seedance-4.5"
```

---

## 6. Team & Scaling Guide

### 6.1 Role Definitions

| Role | Responsibilities | Skills Needed |
|------|------------------|---------------|
| **Platform Engineer** | Core pipeline, backends, FFmpeg, workers | Python, asyncio, GPU, Docker |
| **ML/Video Engineer** | AI models, prompt engineering, quality | Diffusers, Veo API, eval frameworks |
| **Graphics Engineer** | Three.js, shaders, ASCII, compositor | WebGL, GLSL, Three.js, color science |
| **Backend Engineer** | API, queue, billing, auth, scaling | FastAPI, Redis, Postgres, Stripe |
| **DevOps/MLOps** | CI/CD, GPU clusters, monitoring, cost | K8s, Terraform, Prometheus, Grafana |
| **Product Designer** | Templates, scene archetypes, brand kits | Figma, motion design, video UX |

### 6.2 Scaling Targets

| Metric | Target | Current |
|--------|--------|---------|
| Concurrent renders | 50 | 3 |
| Avg render cost | <$0.10/min | ~$0.50/min (AI) |
| Queue latency (p95) | <30s | ~2min |
| API p99 latency | <200ms | N/A |
| Uptime | 99.9% | N/A |

### 6.3 GPU Cluster Strategy

```
┌────────────────────────────────────────────┐
│           GPU POOL MANAGER                  │
├────────────────────────────────────────────┤
│  ASCII Workers (RTX 4090 × 8)              │
│  → 2-4 concurrent per GPU (VRAM ~8GB each) │
├────────────────────────────────────────────┤
│  Hybrid Workers (A100 × 4)                 │
│  → 1 concurrent per GPU (VRAM ~20GB)       │
├────────────────────────────────────────────┤
│  AI Video (Cloud API)                      │
│  → No local GPU, Hyper MCP handles         │
└────────────────────────────────────────────┘
```

---

## 7. File Index — Quick Navigation

```
H:\OPEN MOVIE\
├── HANDOFF.md                    ← THIS FILE
├── project.yaml                  ← Sample project (LLM film)
├── src/open_movie_core/
│   ├── __init__.py               ← Public exports
│   ├── brief.py                  ← ProjectBrief, Scene, CameraPath, AudioBrief
│   ├── pipeline.py               ← OpenMoviePipeline (main orchestration)
│   ├── cli.py                    ← `om` command entry point
│   ├── backends/
│   │   ├── base.py               ← VideoBackend ABC, Registry, @register_backend
│   │   ├── ascii_backend.py      ← Three.js + Puppeteer → frames
│   │   ├── ai_video_backend.py   ← Hyper MCP (Veo/Seedance/Kling)
│   │   └── hybrid_backend.py     ← Planner + Compositor + Stabilizer
│   ├── audio/
│   │   └── generator.py          ← ProceduralAudioGenerator (score.py port)
│   └── ffmpeg/
│       └── encoder.py            ← FFmpegEncoder (async, frames + audio)
├── skills/
│   ├── open-movie-core/SKILL.md
│   ├── open-movie-ascii/SKILL.md
│   ├── open-movie-ai-video/SKILL.md
│   ├── open-movie-hybrid/SKILL.md
│   └── open-movie-saas/SKILL.md
├── agents/                       ← Agent definitions (explorer, verifier, etc.)
├── docs/                         ← Architecture, API docs
├── tests/                        ← pytest suite
└── scripts/                      ← Utility scripts
```

---

## 8. Commands Reference

```bash
# Project management
om init --brief project.yaml [--type explainer] [--force]
om validate --brief project.yaml

# Rendering
om render --brief project.yaml --output out.mp4 [--backend auto|ascii|ai_video|hybrid] [--resume] [--dry-run]
om scene --brief project.yaml --scene vortex --output vortex.mp4

# Audio
om audio --brief project.yaml --output score.wav

# Diagnostics
om doctor
om backends

# SaaS (future)
om api serve                    # Start API server
om worker start --type ascii    # Start worker
om queue status                 # Queue depth, workers
```

---

## 9. Contacts & Resources

| Resource | Link/Location |
|----------|---------------|
| **Hyper MCP** | `https://app.hyperfx.ai/mcp` (API key required) |
| **FFmpeg builds** | `https://www.gyan.dev/ffmpeg/builds/` |
| **Three.js r149** | `https://unpkg.com/three@0.149.0/build/three.min.js` |
| **JetBrains Mono** | `https://github.com/JetBrains/JetBrainsMono` |
| **EBU R128 Spec** | `https://tech.ebu.ch/docs/tech/tech3344.pdf` |

---

## 10. Immediate Next Steps (Copy-Paste Ready)

```bash
# 1. Verify environment
cd H:\OPEN MOVIE
om doctor

# 2. Test ASCII render (fastest, no API keys needed)
om render --brief project.yaml --backend ascii --output test_ascii.mp4

# 3. Configure Hyper MCP for AI backend
# - Get API key from https://app.hyperfx.ai
# - Set HYPER_API_KEY env var
# - Test: om render --brief project.yaml --backend ai_video --output test_ai.mp4

# 4. Test hybrid (requires both above working)
om render --brief project.yaml --backend hybrid --output test_hybrid.mp4

# 5. Create your first custom project
om init --type explainer --brief my_project.yaml
# Edit my_project.yaml...
om validate --brief my_project.yaml
om render --brief my_project.yaml --backend hybrid --output my_video.mp4
```

---

## 11. Decision Log (For Future Reference)

| Date | Decision | Context | Alternatives Considered |
|------|----------|---------|------------------------|
| 2026-11-02 | YAML brief over JSON | Git-diffable, comments, human-readable | JSON (stricter), TOML (less common) |
| 2026-11-02 | Three.js + ASCII shader | Deterministic, code-controllable, unique aesthetic | Pure Python (slow), Terminal recording (not scalable) |
| 2026-11-02 | Hyper MCP for AI video | Unified interface, multiple models, managed infra | Direct APIs (more code), Local models (GPU cost) |
| 2026-11-02 | Procedural audio default | Zero cost, deterministic, EBU R128 compliant | AI music (expensive, non-deterministic), Stock (licensing) |
| 2026-11-02 | Skills as portable units | Reusable across projects, composable for SaaS | Monolithic package (harder to maintain) |

---

## 12. Glossary

| Term | Definition |
|------|------------|
| **ProjectBrief** | YAML file defining video: scenes, timing, camera, audio, output |
| **Backend** | Rendering engine: ASCII, AI Video, Hybrid |
| **Scene** | Time-bounded segment with description, camera, parameters |
| **Element** | Hybrid: atomic visual unit classified as CODE / AI_VIDEO / AI_TEXTURE |
| **Planner** | Hybrid: classifies scene description into typed elements |
| **Compositor** | Hybrid: blends code + AI frames with blend modes |
| **Scene Chaining** | AI: using last frame of clip N as image prompt for clip N+1 |
| **Checkpoint** | Frame index saved to disk; enables resume after crash |
| **LUFS** | Loudness Units Full Scale (EBU R128 loudness standard) |
| **CRF** | Constant Rate Factor (x264 quality, 0-51, lower=better) |

---

*Document version: 1.0 | Generated: 2026-11-02 | Next review: Phase 0 complete*