# OPEN MOVIE

> **Universal Video Generation Pipeline** — One declarative brief, multiple rendering backends (ASCII, AI Video, Hybrid), production-ready SaaS architecture.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active%20Development-yellow.svg)]()

## Overview

OPEN MOVIE transforms a single YAML project brief into finished videos through **three interchangeable backends**:

| Backend | Style | Speed | Cost | Deterministic |
|---------|-------|-------|------|---------------|
| **ASCII** | Terminal/hacker aesthetic | ~8 fps | Free | ✅ Yes |
| **AI Video** | Photorealistic (Veo/Seedance/Kling) | ~0.5 fps | $0.50/s | ❌ No |
| **Hybrid** | Best of both worlds | ~4 fps | $0.10/s | Partial |

```yaml
# One brief → any backend
project:
  id: "om-001"
  title: "My Video"
  duration: 148
  resolution: "1080x1920"
  fps: 30

scenes:
  - id: "intro"
    start: 0
    end: 10
    description: "Opening hook with bold typography"
  - id: "demo"
    start: 10
    end: 60
    description: "Live coding demonstration"
```

```bash
om render --brief project.yaml --backend hybrid --output video.mp4
```

## Quick Start

### Prerequisites

- **Python 3.10+** with `numpy`, `scipy`, `pyyaml`, `pillow`
- **FFmpeg** (with libx264, aac)
- **Node.js 18+** (for ASCII backend Puppeteer)
- **Google Chrome** (for ASCII backend)
- **Hyper MCP API key** (for AI Video backend) — [get one](https://app.hyperfx.ai)

### Installation

```bash
git clone https://github.com/yourusername/open-movie.git
cd open-movie

# Python deps
pip install -r requirements.txt

# Verify environment
om doctor
```

### First Render (ASCII — no API keys needed)

```bash
# Test with included sample project
om render --brief project.yaml --backend ascii --output test.mp4

# Or generate your own project
om init --type explainer --brief my_video.yaml
# Edit my_video.yaml...
om render --brief my_video.yaml --backend ascii --output my_video.mp4
```

### Full Quality (Hybrid — requires Hyper MCP)

```bash
export HYPER_API_KEY="your_key_here"
om render --brief project.yaml --backend hybrid --output final.mp4
```

## Architecture

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
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

| Module | Purpose |
|--------|---------|
| `brief.py` | Declarative spec: ProjectBrief, Scene, CameraPath, AudioBrief |
| `pipeline.py` | Orchestration: backend selection, progress, checkpoints, audio+encode |
| `backends/base.py` | Abstract `VideoBackend` + `@register_backend` decorator |
| `backends/ascii_backend.py` | Three.js → WebGLRenderTarget → ASCII shader (5×SSAA, Bayer dither) |
| `backends/ai_video_backend.py` | Hyper MCP (Veo 3.1, Seedance 4.5, Kling 3.0) + scene chaining |
| `backends/hybrid_backend.py` | Planner (CODE/AI classification) + Compositor + Temporal Stabilizer |
| `audio/generator.py` | Procedural ambient (Am9/Fmaj7/Dm9/Em7, 60 BPM, -16 LUFS) |
| `ffmpeg/encoder.py` | Async FFmpeg wrapper with progress callbacks |
| `cli.py` | `om` command: init, validate, render, scene, audio, doctor, backends |

## Project Brief Schema

```yaml
project:
  id: "unique-id"
  title: "Video Title"
  duration: 148          # seconds
  resolution: "1080x1920"
  fps: 30
  aspect: "9:16"

pipeline:
  backend: "hybrid"      # auto | ascii | ai_video | hybrid
  quality: "high"

scenes:
  - id: "scene_name"
    start: 0
    end: 30
    description: "Visual description for prompt engineering"
    parameters:
      character_consistency: "token for character lock"
      environment_consistency: "token for setting lock"
      lighting: "golden hour, volumetric"
    camera:
      type: "dolly"      # dolly | orbit | static | keyframe
      keyframes:
        - time: 0
          position: [0, 0, 10]
        - time: 30
          position: [0, 0, -100]
      easing: "ease-in-out"
    backend_hint: "hybrid"  # optional override

audio:
  style: "ambient"       # ambient | cinematic | electronic | orchestral
  bpm: 60
  key: "Am"
  progression: ["Am9", "Fmaj7", "Dm9", "Em7"]
  loudnorm_target: -16   # EBU R128 LUFS
  generator: "procedural"

output:
  format: "mp4"
  codec: "libx264"
  crf: 18
  preset: "slow"
  pix_fmt: "yuv420p"
  audio_codec: "aac"
  audio_bitrate: "192k"
```

## Video Types (Templates)

```bash
# Built-in templates
om init --type explainer --brief project.yaml    # Technical tutorials
om init --type short --brief reel.yaml           # TikTok/Reels/Shorts
om init --type datastory --brief data.yaml       # Analytics dashboards
om init --type talking_head --brief avatar.yaml  # AI avatar narration
om init --type product_demo --brief demo.yaml    # SaaS walkthroughs
om init --type music_viz --brief viz.yaml        # Audio-reactive
om init --type course --brief lesson.yaml        # Educational
om init --type ad_creative --brief ad.yaml       # Paid social ads
```

## CLI Reference

```bash
# Project management
om init --brief project.yaml [--type explainer] [--force]
om validate --brief project.yaml

# Rendering
om render --brief project.yaml --output out.mp4 [--backend auto|ascii|ai_video|hybrid] [--resume] [--dry-run]
om scene --brief project.yaml --scene vortex --output vortex.mp4

# Audio only
om audio --brief project.yaml --output score.wav

# Diagnostics
om doctor                    # Check FFmpeg, Node, Chrome, Python deps
om backends                  # List registered backends with capabilities
```

## Skills (Portable Modules)

Each backend is a **universal skill** — reusable across projects:

| Skill | Path | Description |
|-------|------|-------------|
| `open-movie-core` | `skills/open-movie-core/` | Pipeline orchestration, brief schema, registry |
| `open-movie-ascii` | `skills/open-movie-ascii/` | Three.js + ASCII shader backend |
| `open-movie-ai-video` | `skills/open-movie-ai-video/` | Hyper MCP AI video generation |
| `open-movie-hybrid` | `skills/open-movie-hybrid/` | Code + AI composition (Planner + Compositor) |
| `open-movie-saas` | `skills/open-movie-saas/` | API, billing, queue, multi-tenant |

## SaaS Roadmap

The `open-movie-saas` skill provides a production-ready service layer:

- **FastAPI** + JWT auth + Redis/BullMQ job queue
- **Stripe billing** with credit-based plans (Free/Creator/Pro/Team/Enterprise)
- **Autoscaling workers** (K8s HPA, GPU-aware scheduling)
- **Python SDK** for integrators: `pip install openmovie`

```python
from openmovie import OpenMovieClient

client = OpenMovieClient(api_key="om_live_...")
project = client.create_project("My Explainer", type="explainer")
job = client.start_render(project.id, backend="hybrid")
url = client.wait_for_completion(job.id, timeout=1800)
client.download(project.id, "./output.mp4")
```

## Development

```bash
# Run tests
pytest tests/ -v --cov=open_movie_core

# Type checking
mypy src/open_movie_core

# Lint
ruff src/open_movie_core

# Build docs
mkdocs serve
```

## Contributing

1. Fork the repo
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Add tests for new functionality
4. Ensure `pytest`, `mypy`, `ruff` pass
5. Submit PR with clear description

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- **Three.js** — 3D rendering foundation
- **Hyper MCP** — Unified AI video model access
- **FFmpeg** — Video encoding backbone
- **JetBrains Mono** — ASCII font
- **EBU R128** — Loudness standard

---

**Built for creators who want code-level control over video generation.**