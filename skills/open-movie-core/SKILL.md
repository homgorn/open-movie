# Skill: open-movie-core

## Universal Video Generation Pipeline Orchestrator

This skill provides the core orchestration layer for the OPEN MOVIE service — a unified pipeline that can generate videos through multiple backends (code-driven, AI-driven, hybrid) with a consistent interface.

## When to Use

- Starting a new video generation project in OPEN MOVIE
- Need to coordinate multiple generation backends
- Building a SaaS service around video generation
- Need deterministic, reproducible video pipelines

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     OPEN MOVIE CORE                          │
├─────────────────────────────────────────────────────────────┤
│  Project Brief (YAML)                                        │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐   │
│  │ Pipeline│───▶│  Render │───▶│  Audio  │───▶│  Encode │   │
│  │ Selector│    │ Engine  │    │  Mixer  │    │  (FFmpeg)│  │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘   │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Backend Adapters                        │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │    │
│  │  │  ASCII   │ │  AI Vid  │ │ Hybrid   │ │ Custom │  │    │
│  │  │ (Three.js)│ │ (Veo/    │ │ (Code+AI)│ │ Plugin │  │    │
│  │  │          │ │  Seedance)│ │          │ │        │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Core Concepts

### Project Brief (project.yaml)

Every video project starts with a declarative brief:

```yaml
project:
  id: "om-2026-001"
  title: "What It's Like to Be an LLM"
  duration: 148  # seconds
  resolution: "1080x1920"
  fps: 30
  aspect: "9:16"

pipeline:
  backend: "ascii"  # ascii | ai-video | hybrid | auto
  quality: "high"   # draft | standard | high | ultra

scenes:
  - id: "void"
    start: 0
    end: 17
    description: "Empty space, cursor blinking"
  - id: "vortex"
    start: 17
    end: 47
    description: "Token spiral forming"
  - id: "sea"
    start: 47
    end: 70
    description: "Ocean of tokens"
  - id: "library"
    start: 70
    end: 96
    description: "Cathedral of knowledge"
  - id: "attention"
    start: 96
    end: 118
    description: "Attention lattice"
  - id: "convergence"
    start: 118
    end: 136
    description: "Rings converging to gate"
  - id: "finale"
    start: 136
    end: 148
    description: "Final cursor, silence"

audio:
  style: "ambient"
  bpm: 60
  key: "Am"
  progression: ["Am9", "Fmaj7", "Dm9", "Em7"]
  loudnorm: -16  # LUFS

output:
  format: "mp4"
  codec: "libx264"
  crf: 18
  preset: "slow"
  audio_codec: "aac"
  audio_bitrate: "192k"
```

### Pipeline Interface

All backends implement the same interface:

```python
class VideoBackend(ABC):
    @abstractmethod
    def render_frame(self, scene: Scene, t: float, frame_idx: int) -> np.ndarray:
        """Render a single frame at time t"""
        pass

    @abstractmethod
    def render_segment(self, scene: Scene, start_frame: int, end_frame: int) -> List[Path]:
        """Render a frame range, return paths"""
        pass

    @abstractmethod
    def get_capabilities(self) -> BackendCapabilities:
        """Return what this backend can do"""
        pass
```

### Scene Definition

```python
@dataclass
class Scene:
    id: str
    start: float
    end: float
    description: str
    parameters: Dict[str, Any]  # Backend-specific params
    camera: CameraPath
    audio_cues: List[AudioCue]

@dataclass
class CameraPath:
    type: str  # "dolly" | "orbit" | "static" | "custom"
    keyframes: List[Keyframe]
    easing: str = "ease-in-out"
```

## Commands

```bash
# Initialize a new project
om init --brief project.yaml

# Validate project brief
om validate --brief project.yaml

# Render full video
om render --brief project.yaml --output outputs/final.mp4

# Render specific scene
om render --brief project.yaml --scene void --output outputs/void.mp4

# Render with specific backend
om render --brief project.yaml --backend ascii

# Generate audio only
om audio --brief project.yaml --output outputs/score.wav

# Check pipeline health
om doctor

# List available backends
om backends
```

## Configuration

```yaml
# config.yaml
core:
  work_dir: "./work"
  cache_dir: "./cache"
  max_parallel_frames: 4
  frame_timeout: 300  # seconds

backends:
  ascii:
    enabled: true
    chrome_path: "C:/Program Files/Google/Chrome/Application/chrome.exe"
    puppeteer_args: ["--no-sandbox", "--disable-gpu"]
  
  ai_video:
    enabled: true
    provider: "hyper"  # hyper | direct
    models:
      - "veo-3.1"
      - "seedance-4.5"
      - "kling-3.0"
  
  hybrid:
    enabled: true
    code_weight: 0.6
    ai_weight: 0.4

ffmpeg:
  path: "ffmpeg"
  threads: 0  # auto
  hwaccel: "auto"
```

## Guardrails

- **Deterministic rendering**: Same brief + same seed = identical output
- **No external dependencies in core**: Backends are plugins
- **Checkpointing**: Every 100 frames, write progress
- **Resume capability**: `--resume` picks up from last checkpoint
- **Validation gates**: Run `om validate` before any render

## Integration with Other Skills

| Skill | Provides |
|-------|----------|
| `open-movie-ascii` | Three.js + ASCII shader backend |
| `open-movie-ai-video` | AI video generation backend |
| `open-movie-hybrid` | Combined code+AI backend |
| `open-movie-saas` | API, billing, multi-tenant |

## Extension Points

### Custom Backend

```python
# backends/my_backend.py
from open_movie_core import VideoBackend, BackendCapabilities

class MyBackend(VideoBackend):
    def render_frame(self, scene, t, frame_idx):
        # Your rendering logic
        return frame_array
    
    def get_capabilities(self):
        return BackendCapabilities(
            max_resolution=(1920, 1080),
            supports_audio=True,
            supports_transparency=False,
            estimated_fps=5.0
        )

# Register in project.yaml:
# pipeline:
#   backend: "my_backend"
#   backend_path: "./backends/my_backend.py"
```

### Custom Audio Generator

```python
# audio/generators/my_composer.py
from open_movie_core import AudioGenerator

class MyComposer(AudioGenerator):
    def generate(self, brief: ProjectBrief) -> Path:
        # Generate score.wav
        return score_path
```

## File Structure

```
H:\OPEN MOVIE\
├── src/
│   └── open_movie_core/
│       ├── __init__.py
│       ├── brief.py          # Project brief parsing/validation
│       ├── pipeline.py       # Main orchestration
│       ├── backends/         # Backend base classes
│       ├── audio/            # Audio generation
│       ├── ffmpeg/           # FFmpeg wrapper
│       └── cli.py            # CLI entry point
├── pipelines/
│   ├── ascii/                # ASCII pipeline (separate skill)
│   ├── ai-video/             # AI video pipeline (separate skill)
│   └── hybrid/               # Hybrid pipeline (separate skill)
├── skills/
│   ├── open-movie-core/      # THIS skill
│   ├── open-movie-ascii/
│   ├── open-movie-ai-video/
│   ├── open-movie-hybrid/
│   └── open-movie-saas/
├── agents/
│   ├── explorer.md
│   ├── implementer.md
│   ├── verifier.md
│   └── runner.md
├── docs/
│   ├── architecture.md
│   ├── backend-api.md
│   └── project-brief-schema.json
├── tests/
│   ├── test_brief.py
│   ├── test_pipeline.py
│   └── fixtures/
├── data/
│   ├── fonts/
│   ├── shaders/
│   └── audio/
├── outputs/
├── scripts/
│   ├── render.py
│   ├── validate.py
│   └── doctor.py
└── config.yaml
```

## Verification Gates

Run before any release:

```bash
om validate --brief project.yaml           # Schema validation
om doctor                                  # Environment check
om render --brief project.yaml --dry-run   # Pipeline dry run
om test --backend ascii                    # Backend self-test
```

---

*Part of the OPEN MOVIE universal skill set. See `open-movie-ascii`, `open-movie-ai-video`, `open-movie-hybrid`, `open-movie-saas` for backend implementations.*