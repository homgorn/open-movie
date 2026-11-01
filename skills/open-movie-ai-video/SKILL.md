# Skill: open-movie-ai-video

## AI Video Generation Backend (Veo, Seedance, Kling, etc.)

This skill implements the **AI-driven video generation** backend for OPEN MOVIE using state-of-the-art video models (Google Veo 3.1, ByteDance Seedance 4.5, Kling 3.0, etc.) via the Hyper MCP or direct APIs.

## When to Use

- Need photorealistic / cinematic quality
- Complex scenes hard to code (nature, humans, physics)
- Rapid prototyping / iteration
- "Impossible camera" shots
- UGC-style content (talking heads, product demos)

## Architecture

```
Project Brief → Scene Prompts → Video Model → Clips → Stitch → Audio → Encode
                     │              │
                     ▼              ▼
              Prompt Engineering  Quality Review
              (per model)         (videos_analyze)
```

## Supported Models

| Model | Provider | Best For | Max Duration | Resolution | Cost |
|-------|----------|----------|--------------|------------|------|
| Veo 3.1 | Google | Cinematic, 4K, long shots | 60s | 4K | High |
| Gemini Omni | Google | Conversational, consistent clips | 10s | 1080p | Medium |
| Seedance 4.5 | ByteDance | Lowest cost, decent quality | 10s | 1080p | Low |
| Kling 3.0 | Kuaishou | Cheap volume | 10s | 1080p | Low |
| Sora | OpenAI | General purpose | 20s | 1080p | High |

## Pipeline Stages

### 1. Scene → Prompt Engineering

```python
# prompts/engine.py
class PromptEngine:
    """Converts scene descriptions to model-optimized prompts"""
    
    MODEL_TEMPLATES = {
        'veo-3.1': """
            {scene_description}
            Camera: {camera_movement}
            Lighting: {lighting}
            Style: Cinematic, 4K, {lens}mm, {aperture}
            Negative: morphing, warping, melting, jelly motion, 
                      slow motion, blurry, low quality, watermark
        """,
        'seedance-4.5': """
            {scene_description}
            {camera_movement}
            {lighting}
            High quality, detailed, 1080p
        """,
        'kling-3.0': """
            {scene_description}, {camera_movement}, {lighting},
            masterpiece, best quality, ultra-detailed
        """
    }
    
    def build_prompt(self, scene: Scene, model: str) -> str:
        template = self.MODEL_TEMPLATES[model]
        return template.format(
            scene_description=self._enhance_description(scene),
            camera_movement=self._camera_prompt(scene.camera),
            lighting=self._lighting_prompt(scene.lighting),
            lens=scene.lens or 35,
            aperture=scene.aperture or "f/2.8"
        )
    
    def _enhance_description(self, scene: Scene) -> str:
        # Add consistency tokens for character/environment
        base = scene.description
        if scene.character:
            base += f", {scene.character.consistency_token}"
        if scene.environment:
            base += f", {scene.environment.consistency_token}"
        return base
```

### 2. Scene Chaining (Critical for Consistency)

```python
# chaining.py
class SceneChainer:
    """Ensures visual consistency across AI-generated clips"""
    
    def __init__(self, model: str):
        self.model = model
        self.reference_frames = {}  # scene_id -> last_frame
    
    async def generate_scene(self, scene: Scene, prev_scene: Scene = None) -> Clip:
        prompt = self.prompt_engine.build_prompt(scene, self.model)
        
        # Use last frame of previous scene as image prompt for continuity
        image_prompt = None
        if prev_scene and prev_scene.id in self.reference_frames:
            image_prompt = self.reference_frames[prev_scene.id]
        
        # Generate
        clip = await self._generate(prompt, image_prompt)
        
        # Store last frame for next scene
        self.reference_frames[scene.id] = clip.last_frame
        
        # Quality review
        review = await self._quality_review(clip, scene)
        if not review.passes:
            # Regenerate with adjusted prompt
            clip = await self._regenerate_with_feedback(clip, review)
        
        return clip
    
    async def _generate(self, prompt: str, image_prompt: str = None) -> Clip:
        if self.model.startswith('veo'):
            return await self._generate_veo(prompt, image_prompt)
        elif self.model.startswith('seedance'):
            return await self._generate_seedance(prompt, image_prompt)
        # ... other models
```

### 3. Hyper MCP Integration

```python
# hyper_client.py
class HyperVideoClient:
    """Wrapper for Hyper MCP video tools"""
    
    def __init__(self, mcp_client):
        self.mcp = mcp_client
    
    async def generate(self, prompt: str, model: str, 
                       image_prompt: str = None, **params) -> str:
        """Returns file_id of generated video"""
        result = await self.mcp.call('videos_generate', {
            'prompt': prompt,
            'model': model,
            'image_prompt': image_prompt,
            **params
        })
        return result['file_id']
    
    async def analyze(self, file_id: str, 
                      analysis_type: str = 'quality_review') -> dict:
        return await self.mcp.call('videos_analyze', {
            'file_id': file_id,
            'analysis_type': analysis_type
        })
    
    async def stitch(self, file_ids: List[str]) -> str:
        return await self.mcp.call('videos_stitch', {
            'file_ids': file_ids
        })
    
    async def add_audio(self, video_id: str, audio_id: str) -> str:
        return await self.mcp.call('videos_audio_add', {
            'video_file_id': video_id,
            'audio_file_id': audio_id
        })
    
    async def add_subtitles(self, video_id: str, srt_content: str) -> str:
        return await self.mcp.call('videos_subtitles_burn', {
            'video_file_id': video_id,
            'subtitle_content': srt_content
        })
```

### 4. Audio Generation

```python
# audio/ai_audio.py
class AIAudioGenerator:
    """Generates voiceover, music, sound effects"""
    
    async def generate_voiceover(self, script: str, voice: str = 'default') -> str:
        """Returns audio file_id"""
        return await self.mcp.call('audio_speech_generate', {
            'text': script,
            'voice_id': voice,
            'model': 'elevenlabs'
        })
    
    async def generate_music(self, brief: AudioBrief) -> str:
        # Use procedural generation (like our score.py) or AI music
        # For now, reuse the procedural approach for consistency
        return await self._generate_procedural(brief)
    
    async def generate_sfx(self, cues: List[SFXCue]) -> List[str]:
        # Generate sound effects for specific moments
        pass
```

### 5. Post-Production

```python
# post.py
class PostProduction:
    """Stitch, subtitle, color grade, final encode"""
    
    async def assemble(self, clips: List[Clip], audio: AudioTrack, 
                       subtitles: SubtitleTrack) -> str:
        # 1. Stitch video clips
        stitched = await self.hyper.stitch([c.file_id for c in clips])
        
        # 2. Add audio
        with_audio = await self.hyper.add_audio(stitched, audio.file_id)
        
        # 3. Burn subtitles
        final = await self.hyper.add_subtitles(with_audio, subtitles.srt)
        
        # 4. Download and verify
        local_path = await self._download(final)
        await self._verify(local_path)
        
        return local_path
```

## Configuration

```yaml
# ai-video-config.yaml
models:
  primary: "veo-3.1"
  fallback: ["seedance-4.5", "kling-3.0"]
  
generation:
  max_concurrent: 3
  timeout_per_clip: 300  # seconds
  retry_attempts: 2
  
prompt_engineering:
  consistency_tokens: true
  negative_prompts: true
  camera_vocabulary: true
  lighting_vocabulary: true
  
quality_review:
  enabled: true
  criteria:
    - "matches_prompt"
    - "visual_consistency"
    - "no_artifacts"
    - "proper_timing"
  auto_regenerate: true
  max_regenerations: 3
  
chaining:
  use_last_frame: true
  overlap_frames: 2
  crossfade_duration: 0.5
  
audio:
  voice_provider: "elevenlabs"
  music_generator: "procedural"  # or "ai"
  loudnorm_target: -16
  
post_production:
  subtitle_style: "tiktok"  # or "standard", "karaoke"
  color_grade: "cinematic"
  output_codec: "libx264"
  crf: 18
```

## Scene Prompt Library

```yaml
# prompts/scenes.yaml
scenes:
  void:
    description: |
      Infinite dark void, single blinking cursor in center,
      minimal, high contrast, philosophical atmosphere
    camera: "static, slight micro-movements"
    lighting: "single point light on cursor, otherwise pitch black"
    model_params:
      veo-3.1:
        duration: 17
        aspect_ratio: "9:16"
  
  vortex:
    description: |
      Particles forming a logarithmic spiral, glowing tokens
      emerging from center, rotating, accelerating
    camera: "slow dolly forward, subtle rotation"
    lighting: "bioluminescent particles, volumetric glow"
    model_params:
      veo-3.1:
        duration: 30
        aspect_ratio: "9:16"
  
  sea:
    description: |
      Vast ocean of glowing text characters, waves of data,
      rays of light piercing down from above
    camera: "aerial dolly, descending into the sea"
    lighting: "god rays, caustics, bioluminescent waves"
  
  library:
    description: |
      Infinite cathedral-like library, golden glowing books,
      arches stretching to infinity, dust motes in light beams
    camera: "slow tracking shot down central aisle"
    lighting: "warm golden hour, volumetric dust, rim light"
  
  attention:
    description: |
      Geometric lattice of connected nodes, light pulses
      traveling along edges, mathematical beauty
    camera: "orbit around lattice, dolly through center"
    lighting: "cool blue-white, edge glow, pulse animation"
  
  convergence:
    description: |
      Concentric rings collapsing toward center,
      forming a portal/gate, energy buildup
    camera: "straight toward center, accelerating"
    lighting: "intense white flash at convergence, lens flare"
  
  finale:
    description: |
      Single cursor in vast darkness, faint echo rings
      expanding and fading, profound silence
    camera: "static"
    lighting: "minimal, cursor glow only"
```

## Cost Estimation

| Model | Cost/10s | 148s Video (15 clips) | Notes |
|-------|----------|----------------------|-------|
| Veo 3.1 | ~$0.50-1.00 | $7.50-15.00 | Highest quality |
| Gemini Omni | ~$0.10-0.30 | $1.50-4.50 | Good consistency |
| Seedance 4.5 | ~$0.02-0.05 | $0.30-0.75 | Cheapest |
| Kling 3.0 | ~$0.03-0.08 | $0.45-1.20 | Good volume |

## Integration with open-movie-core

```python
# backends/ai_video_backend.py
from open_movie_core import VideoBackend, BackendCapabilities
from typing import List
from pathlib import Path

class AIVideoBackend(VideoBackend):
    def __init__(self, config_path: Path):
        self.config = load_config(config_path)
        self.hyper = HyperVideoClient(config_path)
        self.prompt_engine = PromptEngine()
        self.chainer = SceneChainer(self.config['models']['primary'])
    
    async def render_segment(self, scene: Scene, 
                            start_frame: int, end_frame: int) -> List[Path]:
        # Generate clip for this scene
        clip = await self.chainer.generate_scene(scene)
        
        # Download clip
        local_clip = await self.hyper.download(clip.file_id)
        
        # Extract frames if needed for frame-level control
        frames = self._extract_frames(local_clip, start_frame, end_frame)
        
        return frames
    
    async def render_full(self, brief: ProjectBrief) -> Path:
        # Generate all scenes
        clips = []
        prev_scene = None
        for scene in brief.scenes:
            clip = await self.chainer.generate_scene(scene, prev_scene)
            clips.append(clip)
            prev_scene = scene
        
        # Generate audio
        audio = await self._generate_audio(brief)
        
        # Generate subtitles
        subtitles = self._generate_subtitles(brief)
        
        # Assemble
        final = await self.post.assemble(clips, audio, subtitles)
        
        return Path(final)
    
    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            max_resolution=(1920, 1080),
            max_fps=30,
            max_duration=60,  # per clip
            supports_transparency=False,
            supports_audio=True,
            estimated_fps=0.5,  # clips per minute
            deterministic=False,  # AI is non-deterministic
            gpu_required=False,  # Cloud inference
            cost_per_second=0.10  # approximate
        )
```

## Quality Control

```python
# quality/gates.py
class QualityGates:
    """Automated quality checks for AI-generated clips"""
    
    async def check_clip(self, clip: Clip, scene: Scene) -> QualityReport:
        # 1. Prompt adherence
        analysis = await self.hyper.analyze(clip.file_id, 'general')
        prompt_match = self._score_prompt_match(analysis, scene)
        
        # 2. Technical quality
        quality = await self.hyper.analyze(clip.file_id, 'quality_review')
        
        # 3. Consistency with previous
        consistency = 1.0
        if scene.prev_clip:
            consistency = self._compare_frames(
                scene.prev_clip.last_frame,
                clip.first_frame
            )
        
        return QualityReport(
            prompt_adherence=prompt_match,
            technical_quality=quality.score,
            consistency=consistency,
            passes=all([
                prompt_match > 0.7,
                quality.score > 0.6,
                consistency > 0.8
            ])
        )
```

## File Structure

```
skills/open-movie-ai-video/
├── SKILL.md
├── src/
│   ├── hyper_client.py
│   ├── prompt_engine.py
│   ├── chaining.py
│   ├── audio/
│   │   ├── ai_audio.py
│   │   └── procedural_fallback.py
│   ├── post.py
│   └── quality/
│       └── gates.py
├── prompts/
│   ├── engine.py
│   ├── scenes.yaml
│   └── templates/
│       ├── veo-3.1.j2
│       ├── seedance-4.5.j2
│       └── kling-3.0.j2
├── config/
│   └── ai-video-config.yaml
├── tests/
│   ├── test_prompts.py
│   ├── test_chaining.py
│   └── test_quality.py
└── assets/
    └── reference_images/
```

## Model-Specific Optimizations

### Veo 3.1 (Cinematic Hero Shots)
- Use for: Opening, hero moments, complex physics
- Prompt: Detailed cinematography vocab
- Image prompt: Essential for consistency
- Duration: Up to 60s

### Gemini Omni (Conversational Consistency)
- Use for: Dialogue scenes, consistent character
- Prompt: Natural language, iterative
- Image prompt: Auto from previous
- Duration: ~10s

### Seedance 4.5 (Volume/Filler)
- Use for: Background, transitions, simple motions
- Prompt: Concise, descriptive
- No image prompt needed
- Duration: 10s

---

*Backend skill for OPEN MOVIE. Requires `open-movie-core` and Hyper MCP connection. See `open-movie-ascii`, `open-movie-hybrid` for alternative backends.*