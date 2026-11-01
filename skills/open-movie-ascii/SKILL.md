# Skill: open-movie-ascii

## Three.js + ASCII Shader Video Backend

This skill implements the **code-driven ASCII video generation** backend for OPEN MOVIE. It renders 3D scenes through Three.js, then converts to monospace ASCII characters via a custom WebGL shader — producing the distinctive "terminal aesthetic" video we just created.

## When to Use

- Need deterministic, code-controllable visuals
- Want "hacker/terminal" aesthetic
- Need exact frame-by-frame control
- Building technical/explanatory content
- Require 100% reproducibility (same code = same output)

## Approach

```
Three.js Scene → WebGLRenderTarget → ASCII Shader → Puppeteer → Frames → FFmpeg
                     │                      │
                     ▼                      ▼
              5× SSAA sampling         70-char ramp
              10×8 atlas               Bayer dither
              90×96 grid               1080×1920
```

## Pipeline Stages

### 1. Scene Definition (TypeScript/JS)

```typescript
// scenes/void.ts
export function createVoidScene(params: SceneParams): THREE.Group {
  const group = new THREE.Group();
  
  // Cursor
  const cursor = makeCursor(8, 26, '#eaffff');
  cursor.position.set(0, 0, -118);
  group.add(cursor);
  
  // Pulse halo
  const pulseHalo = makeHalo(12, '#88ffff', 0.3);
  pulseHalo.position.set(0, 0, -120);
  group.add(pulseHalo);
  
  return group;
}
```

### 2. Camera Path

```typescript
// camera.ts
export function cameraPath(t: number): THREE.Vector3 {
  const PHASES = [
    { t: [0, 116], z: (t) => 16 - 3.37 * t },
    { t: [116, 126], z: (t) => -374.9 - 1.69 * (t - 116) },
    { t: [126, 148], z: (t) => -391.8 },
  ];
  
  for (const phase of PHASES) {
    if (t >= phase.t[0] && t <= phase.t[1]) {
      return new THREE.Vector3(
        swayX(t), swayY(t), phase.z(t)
      );
    }
  }
  return new THREE.Vector3(0, 1.3, -414);
}
```

### 3. ASCII Post-Shader

```glsl
// shaders/ascii.frag
uniform sampler2D uScene;
uniform sampler2D uAtlas;
uniform sampler2D uBayer;
uniform vec2 uGrid;      // 90, 96
uniform float uRampLen;  // 70
uniform float uExposure; // 1.0

const string RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$";

void main() {
  // 5× SSAA per cell
  vec2 cell = floor(vUv * uGrid);
  vec2 cellUv = fract(vUv * uGrid);
  vec2 center = (cell + 0.5) / uGrid;
  
  vec3 c0 = sampleScene(center);
  vec3 c1 = sampleScene(center + d);
  // ... c2, c3, c4
  
  float l = luminance(best_color);
  float lg = pow(max(l, 0.0), 0.90);
  float level = smoothstep(0.03, 0.62, lg) * 1.02;
  level *= uExposure;
  
  // Bayer dither
  float bayer = texture2D(uBayer, vUv * uGrid / 8.0).r;
  level += (bayer - 0.5) * 0.02;
  
  // Character selection
  int idx = int(clamp(level * uRampLen, 0.0, uRampLen - 1.0));
  vec2 uv = charUV(idx);
  gl_FragColor = vec4(texture2D(uAtlas, uv).rgb, 1.0);
}
```

### 4. Frame Rendering (Puppeteer)

```javascript
// render.js
const page = await browser.newPage();
await page.goto('file:///.../film.html');
await page.waitForFunction('window.__ready === true');

for (let f = startFrame; f <= endFrame; f++) {
  const t = f / FPS;
  await page.evaluate(t => window.__render(t), t);
  await page.screenshot({ 
    path: `frames/frame_${f}.jpg`, 
    type: 'jpeg', quality: 92 
  });
}
```

### 5. FFmpeg Encoding

```bash
ffmpeg -y -framerate 30 -i frames/frame_%05d.jpg \
  -i score.wav \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -shortest \
  -movflags +faststart output.mp4
```

## Scene Library (Reusable)

| Scene | Duration | Key Elements | Z-Range |
|-------|----------|--------------|---------|
| `void` | 0-17s | Cursor, pulse halo | 16 → -375 |
| `vortex` | 17-47s | Token spiral, rings | -56 → -154 |
| `sea` | 47-70s | Token ocean, grid, rays | -136 → -226 |
| `library` | 70-96s | Walls, rings, tablets | -155 → -277 |
| `attention` | 96-118s | Cylinder, nodes, cones | -240 → -332 |
| `convergence` | 118-136s | Flying rings, swirl | -318 → -379 |
| `finale` | 136-148s | Cursor, echo rings | -414 |

## Configuration

```yaml
# ascii-config.yaml
renderer:
  width: 1080
  height: 1920
  fps: 30
  fov: 58
  near: 0.08
  far: 800

ascii:
  cols: 90
  rows: 96
  cell_width: 48
  cell_height: 80
  font_size: 64
  font_weight: "bold"
  ramp: " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
  ramp_length: 70
  supersampling: 5
  dither: "bayer8"
  atlas: "jetbrains-mono-10x8.png"

camera:
  dolly_speed: 3.37
  sway_amplitude: 0.15
  sway_frequency: 0.3
  final_position: [0, 1.3, -414]

performance:
  chrome_path: "C:/Program Files/Google/Chrome/Application/chrome.exe"
  headless: true
  max_concurrent: 1
  frame_timeout_ms: 30000
  checkpoint_interval: 100
```

## Integration with open-movie-core

```python
# backends/ascii_backend.py
from open_movie_core import VideoBackend, BackendCapabilities
from pathlib import Path
import subprocess
import json

class ASCIIBackend(VideoBackend):
    def __init__(self, config_path: Path):
        self.config = load_config(config_path)
        self.work_dir = Path(self.config['work_dir'])
    
    def render_segment(self, scene: Scene, start: int, end: int) -> List[Path]:
        # Generate scene-specific film.html
        film_html = self._generate_film_html(scene)
        
        # Run Puppeteer renderer
        frames = self._render_frames(film_html, start, end)
        
        return frames
    
    def _generate_film_html(self, scene: Scene) -> str:
        # Use Jinja2 template with scene parameters
        template = load_template('film.html.j2')
        return template.render(scene=scene, config=self.config)
    
    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            max_resolution=(1080, 1920),
            max_fps=30,
            supports_transparency=False,
            supports_audio=True,
            estimated_fps=8.0,  # frames/second rendering speed
            deterministic=True,
            gpu_required=True
        )
```

## Reusability Patterns

### Parameterizable Scenes

```typescript
// scenes/parametric/vortex.ts
export interface VortexParams {
  particleCount: number;
  spiralTurns: number;
  colorScheme: 'cool' | 'warm' | 'rainbow';
  ringCount: number;
  speed: number;
}

export function createVortex(params: VortexParams): THREE.Group {
  // All visual params driven by config
}
```

### Scene Composition

```typescript
// composer.ts
export function composeFilm(scenes: SceneDef[]): FilmSpec {
  return {
    scenes: scenes.map(s => ({
      ...s,
      camera: interpolateCamera(s.camera, s.next?.camera),
      audio: crossfadeAudio(s.audio, s.next?.audio),
      transition: s.transition || 'cut'
    }))
  };
}
```

## Performance Targets

| Metric | Target | Measured |
|--------|--------|----------|
| Frame render time | < 500ms | ~250-900ms |
| 148s video (4440 frames) | < 45 min | ~20-60 min |
| Memory (Chrome) | < 2GB | ~1.2GB |
| Determinism | 100% | ✅ Verified |

## Quality Gates

```bash
# Visual regression
om-ascii test --scene void --compare baseline/void.png

# Metrics check
python analyze.py stills/*.png
# mean: 0.05-0.12, p90: 0.3-0.5, coverage >0.05: 0.12-0.22

# Audio loudness
ffmpeg -i score.wav -af loudnorm=I=-16:print_format=json -f null -
```

## File Structure

```
skills/open-movie-ascii/
├── SKILL.md
├── src/
│   ├── film.html.j2          # Jinja2 template
│   ├── shaders/
│   │   ├── ascii.vert
│   │   └── ascii.frag
│   ├── scenes/
│   │   ├── void.ts
│   │   ├── vortex.ts
│   │   ├── sea.ts
│   │   ├── library.ts
│   │   ├── attention.ts
│   │   ├── convergence.ts
│   │   └── finale.ts
│   ├── camera.ts
│   ├── atlas-gen.ts          # Generates font atlas
│   └── bayer-gen.ts          # Generates Bayer matrix
├── render/
│   ├── render.js             # Puppeteer renderer
│   ├── stills.js             # Stop-frame capture
│   └── debug.js              # Scene isolation debug
├── audio/
│   └── score.py              # Procedural score generator
├── config/
│   └── ascii-config.yaml
├── tests/
│   ├── test_shader.py
│   ├── test_camera.py
│   └── fixtures/
└── assets/
    ├── jetbrains-mono-*.woff2
    └── bayer8.png
```

## Migration from Current Film

The current `film/` directory maps to:

| Current | OPEN MOVIE |
|---------|------------|
| `film.html` | `src/film.html.j2` + scene modules |
| `stills.js` | `render/stills.js` |
| `score.py` | `audio/score.py` |
| `render.js` | `render/render.js` (in core) |
| `analyze.py` | `tests/test_metrics.py` |

---

*Backend skill for OPEN MOVIE. Requires `open-movie-core`. See `open-movie-ai-video`, `open-movie-hybrid` for alternative backends.*