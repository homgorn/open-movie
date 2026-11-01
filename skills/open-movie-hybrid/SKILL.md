# Skill: open-movie-hybrid

## Hybrid Code + AI Video Backend

This skill implements the **hybrid backend** for OPEN MOVIE — combining deterministic code-driven rendering (ASCII, procedural, 3D) with AI-generated elements (complex organic forms, photorealistic inserts, talking heads) for the best of both worlds.

## When to Use

- Need both precise control AND organic realism
- Technical explainer with human elements
- Data visualization with photorealistic context
- "Impossible" shots: code the camera/geometry, AI the content
- Cost optimization: AI only where code fails

## Philosophy

```
Code defines:     Camera, timing, geometry, typography, UI, data, structure
AI generates:     Organic textures, human faces, nature, complex physics, style transfer
Compositor blends: Alpha over, color grade, temporal consistency
```

## Hybrid Patterns

### Pattern 1: Code Camera + AI Content
```python
# The camera path is mathematically precise (code)
# The scene content is AI-generated

camera_path = compute_camera_path(scene)  # Deterministic
ai_prompt = build_prompt(scene.description, camera_path)
ai_clip = await generate_ai(ai_prompt, image_prompt=prev_frame)
composited = composite(code_overlay, ai_clip, camera_path)
```

### Pattern 2: AI Base + Code Overlay
```python
# AI generates the "world", code adds precise UI/data layers

ai_background = await generate_ai("vast library, golden light...")
code_overlay = render_ascii_ui(data, camera_path)
final = blend(ai_background, code_overlay, mode="overlay")
```

### Pattern 3: Procedural Structure + AI Texture
```python
# Code creates 3D structure, AI provides textures/materials

geometry = create_procedural_library()  # Code
materials = await ai_textures("golden book leather, dust motes...")
scene = apply_materials(geometry, materials)
frames = render(scene, camera_path)
```

### Pattern 4: Code Keyframes + AI Interpolation
```python
# Code defines keyframes, AI interpolates between them

keyframes = [frame_0, frame_30, frame_60, frame_90]  # Code rendered
interpolated = await ai_interpolate(keyframes, method="flow")
# Or: use AI video model with first/last frame as image prompts
```

## Pipeline Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    HYBRID PIPELINE                              │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Project Brief                                                  │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────┐                                           │
│  │  Scene Planner  │  ──▶ Assigns each element: CODE | AI     │
│  └────────┬────────┘                                           │
│           │                                                     │
│    ┌──────┴──────┐                                             │
│    ▼             ▼                                             │
│ ┌───────┐   ┌─────────┐                                         │
│ │ CODE  │   │   AI    │                                         │
│ │ Pass  │   │  Pass   │                                         │
│ └───┬───┘   └────┬────┘                                         │
│     │            │                                               │
│     └──────┬─────┘                                               │
│            ▼                                                      │
│    ┌───────────────┐                                             │
│    │  COMPOSITOR   │  ◀── Alpha, Color, Temporal Sync           │
│    └───────┬───────┘                                             │
│            │                                                      │
│            ▼                                                      │
│       ┌─────────┐                                                 │
│       │  AUDIO  │                                                 │
│       └────┬────┘                                                 │
│            │                                                      │
│            ▼                                                      │
│       ┌─────────┐                                                 │
│       │ FFMPEG  │                                                 │
│       └─────────┘                                                 │
└────────────────────────────────────────────────────────────────┘
```

## Scene Element Classification

```python
# planner.py
from enum import Enum

class ElementType(Enum):
    CODE = "code"           # Deterministic, exact
    AI_VIDEO = "ai_video"   # Generated clip
    AI_TEXTURE = "ai_texture"  # Texture for 3D object
    AI_INTERP = "ai_interp"    # Frame interpolation
    COMPOSITE = "composite"    # Blend of above

@dataclass
class SceneElement:
    id: str
    type: ElementType
    description: str
    code_renderer: str = None      # e.g. "ascii", "threejs", "procedural"
    ai_model: str = None           # e.g. "veo-3.1", "seedance"
    ai_prompt: str = None
    blend_mode: str = "over"       # over, multiply, screen, add
    opacity: float = 1.0
    timing: Timing = None

class HybridPlanner:
    """Decides which elements are code vs AI"""
    
    RULES = [
        # Camera & timing → ALWAYS CODE
        (lambda e: e.category in ['camera', 'timing'], ElementType.CODE),
        
        # Typography, UI, data viz → CODE
        (lambda e: e.category in ['text', 'ui', 'data', 'charts'], ElementType.CODE),
        
        # Precise geometry → CODE
        (lambda e: e.category in ['geometry', 'grid', 'lattice'], ElementType.CODE),
        
        # Organic, unpredictable → AI
        (lambda e: e.category in ['nature', 'human', 'fluid', 'smoke', 'fire'], ElementType.AI_VIDEO),
        
        # Complex textures → AI_TEXTURE
        (lambda e: e.category in ['material', 'surface', 'skin'], ElementType.AI_TEXTURE),
        
        # Transitions between keyframes → AI_INTERP
        (lambda e: e.category == 'transition', ElementType.AI_INTERP),
    ]
    
    def plan(self, scene: Scene) -> List[SceneElement]:
        elements = self._decompose_scene(scene)
        return [self._classify(e) for e in elements]
```

## Compositor

```python
# compositor.py
class HybridCompositor:
    """Blends code and AI renders with temporal consistency"""
    
    def __init__(self):
        self.color_grade = ColorGradeLUT("cineon")
    
    def composite_frame(self, 
                       code_frame: np.ndarray,
                       ai_frame: np.ndarray,
                       elements: List[SceneElement],
                       t: float) -> np.ndarray:
        """Composite a single frame"""
        
        # Start with code base (usually)
        base = code_frame.copy()
        
        for elem in elements:
            if elem.type == ElementType.AI_VIDEO:
                ai_clip = self._get_ai_clip(elem)
                ai_frame = ai_clip.get_frame(t)
                base = self._blend(base, ai_frame, elem.blend_mode, elem.opacity)
            
            elif elem.type == ElementType.AI_TEXTURE:
                # Applied in 3D render, not here
                pass
            
            elif elem.type == ElementType.CODE:
                # Already in base
                pass
        
        # Global color grade
        return self.color_grade.apply(base)
    
    def _blend(self, base, overlay, mode, opacity):
        if mode == "over":
            return base * (1 - opacity) + overlay * opacity
        elif mode == "multiply":
            return base * (1 - opacity) + base * overlay * opacity
        elif mode == "screen":
            return base * (1 - opacity) + (1 - (1 - base) * (1 - overlay)) * opacity
        elif mode == "add":
            return np.clip(base + overlay * opacity, 0, 1)
        return base
```

## Temporal Consistency

```python
# consistency.py
class TemporalConsistency:
    """Ensures AI elements don't flicker/drift across frames"""
    
    def __init__(self):
        self.feature_tracker = OpticalFlowTracker()
        self.latent_cache = {}  # scene_id -> latent code
    
    def stabilize_ai_clip(self, clip: Clip, reference: Clip) -> Clip:
        """Warp AI clip to match reference motion"""
        # 1. Track features in reference (code) clip
        ref_tracks = self.feature_tracker.track(reference.frames)
        
        # 2. Track features in AI clip
        ai_tracks = self.feature_tracker.track(clip.frames)
        
        # 3. Compute warp field
        warp_field = self._compute_warp(ref_tracks, ai_tracks)
        
        # 4. Apply warp to AI frames
        stabilized = [warp_frame(f, w) for f, w in zip(clip.frames, warp_field)]
        
        return Clip(frames=stabilized, fps=clip.fps)
    
    def latent_consistency(self, scene_id: str, prompt: str) -> str:
        """Reuse latent code for same scene across renders"""
        if scene_id in self.latent_cache:
            return self.latent_cache[scene_id]
        
        latent = self._generate_latent(prompt)
        self.latent_cache[scene_id] = latent
        return latent
```

## Configuration

```yaml
# hybrid-config.yaml
planner:
  # Default classification rules (can be overridden per scene)
  default_code_categories:
    - camera
    - timing
    - text
    - ui
    - data
    - geometry
    - grid
    - lattice
  default_ai_categories:
    - nature
    - human
    - fluid
    - organic
    - atmosphere
  
compositor:
  color_space: "acescg"
  working_gamma: 2.2
  output_gamma: 2.4
  lut: "cineon.cube"
  
  blend_modes:
    default: "over"
    ai_over_code: "over"
    code_over_ai: "screen"
    glow: "add"
  
temporal:
  stabilization: true
  optical_flow: true
  latent_reuse: true
  max_drift_pixels: 2.0
  
ai_models:
  video: "veo-3.1"
  texture: "nano-banana"
  interpolation: "rife"
  
quality:
  min_ai_quality: 0.7
  max_regenerations: 3
  consistency_threshold: 0.85
```

## Example: Our Original Film as Hybrid

| Scene | Code Elements | AI Elements |
|-------|---------------|-------------|
| Void | Camera, cursor, pulse halo | — |
| Vortex | Camera, spiral math, rings | Token particle textures |
| Sea | Camera, grid, rays | Water surface, caustics |
| Library | Camera, architecture, tablets | Book textures, dust motes, lighting |
| Attention | Camera, lattice geometry | Node glow, pulse animation |
| Convergence | Camera, ring geometry | Energy shader, lens flare |
| Finale | Camera, cursor, echo rings | — |

## Cost/Quality Tradeoff

```python
# optimizer.py
class HybridOptimizer:
    """Chooses code vs AI per element based on budget"""
    
    COST_MODEL = {
        ElementType.CODE: 0.0,           # Free (compute only)
        ElementType.AI_VIDEO: 0.50,      # $/10s
        ElementType.AI_TEXTURE: 0.05,    # $/texture
        ElementType.AI_INTERP: 0.10,     # $/second
    }
    
    QUALITY_MODEL = {
        ElementType.CODE: {"control": 1.0, "realism": 0.3},
        ElementType.AI_VIDEO: {"control": 0.4, "realism": 0.95},
        ElementType.AI_TEXTURE: {"control": 0.7, "realism": 0.9},
    }
    
    def optimize(self, scene: Scene, budget: float, 
                 target_quality: float) -> List[SceneElement]:
        """Returns optimal element assignment"""
        # Integer programming / greedy allocation
        pass
```

## Integration with open-movie-core

```python
# backends/hybrid_backend.py
from open_movie_core import VideoBackend, BackendCapabilities
from pathlib import Path
from typing import List

class HybridBackend(VideoBackend):
    def __init__(self, config_path: Path):
        self.config = load_config(config_path)
        self.planner = HybridPlanner()
        self.compositor = HybridCompositor()
        self.consistency = TemporalConsistency()
        self.ai_backend = AIVideoBackend(config_path)  # Reuse AI backend
        self.code_backend = ASCIIBackend(config_path)  # Reuse ASCII backend
    
    def render_segment(self, scene: Scene, 
                       start_frame: int, end_frame: int) -> List[Path]:
        # Plan element assignment
        elements = self.planner.plan(scene)
        
        # Render code elements
        code_frames = self.code_backend.render_segment(scene, start_frame, end_frame)
        
        # Render AI elements
        ai_frames = self._render_ai_elements(scene, elements, start_frame, end_frame)
        
        # Composite
        output_frames = []
        for i, (code_f, ai_f) in enumerate(zip(code_frames, ai_frames)):
            t = (start_frame + i) / self.config['fps']
            comp = self.compositor.composite_frame(code_f, ai_f, elements, t)
            output_frames.append(comp)
        
        # Save frames
        return self._save_frames(output_frames, start_frame)
    
    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            max_resolution=(1920, 1080),
            max_fps=30,
            supports_transparency=True,
            supports_audio=True,
            estimated_fps=4.0,  # Slower due to compositing
            deterministic=False,  # AI portions non-deterministic
            gpu_required=True,
            cost_per_second=0.05  # Hybrid average
        )
```

## File Structure

```
skills/open-movie-hybrid/
├── SKILL.md
├── src/
│   ├── planner.py
│   ├── compositor.py
│   ├── consistency.py
│   ├── optimizer.py
│   └── blender.py
├── config/
│   └── hybrid-config.yaml
├── tests/
│   ├── test_planner.py
│   ├── test_compositor.py
│   └── test_consistency.py
└── assets/
    └── luts/
```

---

*Backend skill for OPEN MOVIE. Requires `open-movie-core`, `open-movie-ascii`, `open-movie-ai-video`. Best of both worlds: code precision + AI realism.*