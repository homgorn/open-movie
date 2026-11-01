"""
Hybrid Backend - Code + AI Composition
"""

from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import asyncio
import logging
import numpy as np
from PIL import Image

from .base import VideoBackend, BackendCapabilities, register_backend, BackendRegistry
from ..brief import ProjectBrief, Scene

logger = logging.getLogger(__name__)


@register_backend("hybrid")
class HybridBackend(VideoBackend):
    """Hybrid backend combining code-driven and AI-driven rendering"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # Sub-backends
        self.code_backend = BackendRegistry.create("ascii", config.get("code_config", {}))
        self.ai_backend = BackendRegistry.create("ai_video", config.get("ai_config", {}))
        
        # Composition settings
        self.color_space = config.get("color_space", "acescg")
        self.default_blend = config.get("default_blend", "over")
        self.temporal_stabilization = config.get("temporal_stabilization", True)
        
        # Planner
        self.planner = HybridPlanner()
        self.compositor = HybridCompositor(
            color_space=self.color_space,
            default_blend=self.default_blend
        )
        
        if self.temporal_stabilization:
            self.stabilizer = TemporalStabilizer()
    
    def get_capabilities(self) -> BackendCapabilities:
        code_caps = self.code_backend.get_capabilities()
        ai_caps = self.ai_backend.get_capabilities()
        
        return BackendCapabilities(
            max_resolution=code_caps.max_resolution,
            max_fps=code_caps.max_fps,
            max_duration=max(code_caps.max_duration, ai_caps.max_duration),
            supports_transparency=True,
            supports_audio=True,
            estimated_fps=min(code_caps.estimated_fps, ai_caps.estimated_fps) * 0.5,
            deterministic=False,
            gpu_required=True,
            cost_per_second=(code_caps.cost_per_second + ai_caps.cost_per_second) / 2,
            supported_formats=["mp4", "mov", "webm"]
        )
    
    def render_frame(self, scene: Scene, t: float, frame_idx: int) -> Image.Image:
        """Render single composite frame"""
        
        # Plan elements for this scene
        elements = self.planner.plan(scene)
        
        # Render code elements
        code_frame = self._render_code_elements(scene, elements, t, frame_idx)
        
        # Render AI elements (async - use cached or generate)
        ai_frame = self._render_ai_elements(scene, elements, t, frame_idx)
        
        # Composite
        return self.compositor.composite(code_frame, ai_frame, elements, t)
    
    def _render_code_elements(self, scene: Scene, elements: List[Dict], 
                            t: float, frame_idx: int) -> Image.Image:
        """Render all CODE-type elements"""
        
        # Filter code elements
        code_elements = [e for e in elements if e.get("type") == "code"]
        
        if not code_elements:
            # Return blank frame
            w, h = self.config.get("width", 1080), self.config.get("height", 1920)
            return Image.new("RGB", (w, h), (0, 0, 0))
        
        # For now, render full scene with code backend and mask
        # In production, would render only code elements
        return self.code_backend.render_frame(scene, t, frame_idx)
    
    def _render_ai_elements(self, scene: Scene, elements: List[Dict],
                          t: float, frame_idx: int) -> Optional[Image.Image]:
        """Render AI elements (from pre-generated clips)"""
        
        ai_elements = [e for e in elements if e.get("type") in ["ai_video", "ai_texture"]]
        
        if not ai_elements:
            return None
        
        # In production, would extract frame from pre-generated AI clips
        # For now, return None (handled in render_full)
        return None
    
    async def render_full(self, brief: ProjectBrief,
                         progress_callback: Callable[[int, int], None] = None) -> str:
        """Full hybrid render pipeline"""
        
        total_frames = int(brief.duration * brief.fps)
        frame_dir = self.work_dir / "frames" / brief.project_id
        frame_dir.mkdir(parents=True, exist_ok=True)
        
        # Phase 1: Plan all scenes
        logger.info("Phase 1: Planning hybrid elements...")
        all_elements = {}
        for scene in brief.scenes:
            all_elements[scene.id] = self.planner.plan(scene)
        
        # Phase 2: Generate AI clips for scenes that need them
        logger.info("Phase 2: Generating AI clips...")
        ai_clips = {}
        ai_scenes = [s for s in brief.scenes 
                     if any(e.get("type") == "ai_video" for e in all_elements[s.id])]
        
        for i, scene in enumerate(ai_scenes):
            if progress_callback:
                progress_callback(i, len(ai_scenes))
            
            clip = await self.ai_backend.generate_clip(scene)
            ai_clips[scene.id] = clip
        
        # Phase 3: Render frames
        logger.info("Phase 3: Rendering and compositing frames...")
        
        # Use code backend for base frames
        code_frames = await self._render_code_frames(brief, frame_dir, progress_callback)
        
        # Composite with AI frames
        if ai_clips:
            await self._composite_ai_frames(brief, code_frames, ai_clips, frame_dir, progress_callback)
        
        # Phase 4: Encode
        logger.info("Phase 4: Encoding...")
        output_path = self.work_dir / f"{brief.project_id}_hybrid.mp4"
        
        # Use FFmpeg to encode frames
        from ..ffmpeg.encoder import FFmpegEncoder, EncodeConfig
        encoder = FFmpegEncoder(EncodeConfig(
            width=self.config.get("width", 1080),
            height=self.config.get("height", 1920),
            fps=brief.fps
        ))
        
        # Generate audio
        from ..audio.generator import ProceduralAudioGenerator
        audio_gen = ProceduralAudioGenerator()
        audio_path = await audio_gen.generate(brief)
        
        frame_pattern = str(frame_dir / "frame_%05d.jpg")
        await encoder.encode_frames(frame_pattern, audio_path, str(output_path))
        
        return str(output_path)
    
    async def _render_code_frames(self, brief: ProjectBrief, 
                                 frame_dir: Path,
                                 progress_callback: Callable) -> List[Path]:
        """Render all frames using code backend"""
        
        # Use code backend's render_full if available, else frame-by-frame
        if hasattr(self.code_backend, 'render_full'):
            # Generate temporary brief for code backend
            code_brief = self._extract_code_brief(brief)
            return await self.code_backend.render_full(code_brief)
        else:
            # Frame by frame
            frames = []
            total = int(brief.duration * brief.fps)
            
            for i in range(total):
                t = i / brief.fps
                # Find scene
                scene = next(s for s in brief.scenes if s.start <= t < s.end)
                
                frame = self.code_backend.render_frame(scene, t, i)
                frame_path = frame_dir / f"frame_{i:05d}.jpg"
                frame.save(frame_path, quality=92)
                frames.append(frame_path)
                
                if progress_callback:
                    progress_callback(i + 1, total)
            
            return frames
    
    async def _composite_ai_frames(self, brief: ProjectBrief,
                                  code_frames: List[Path],
                                  ai_clips: Dict,
                                  frame_dir: Path,
                                  progress_callback: Callable):
        """Composite AI frames over code frames"""
        
        # Extract frames from AI clips
        ai_frames = {}
        for scene_id, clip in ai_clips.items():
            # In production, extract frames from clip file
            # For now, placeholder
            ai_frames[scene_id] = []
        
        # Composite each frame
        for i, code_path in enumerate(code_frames):
            t = i / brief.fps
            scene = next(s for s in brief.scenes if s.start <= t < s.end)
            
            if scene.id in ai_frames and ai_frames[scene.id]:
                ai_frame = ai_frames[scene.id][min(i, len(ai_frames[scene.id]) - 1)]
                code_frame = Image.open(code_path)
                
                # Composite
                elements = self.planner.plan(scene)
                composite = self.compositor.composite(code_frame, ai_frame, elements, t)
                
                # Save composite
                composite.save(code_path, quality=92)
            
            if progress_callback:
                progress_callback(i + 1, len(code_frames))
    
    def _extract_code_brief(self, brief: ProjectBrief) -> ProjectBrief:
        """Create brief with only code-rendered elements"""
        code_scenes = []
        for scene in brief.scenes:
            elements = self.planner.plan(scene)
            code_elements = [e for e in elements if e.get("type") == "code"]
            
            if code_elements:
                code_scene = Scene(
                    id=scene.id,
                    start=scene.start,
                    end=scene.end,
                    description=scene.description,
                    parameters={**scene.parameters, "_hybrid_elements": code_elements},
                    camera=scene.camera,
                    audio=scene.audio
                )
                code_scenes.append(code_scene)
        
        return ProjectBrief(
            project_id=brief.project_id,
            title=brief.title,
            duration=brief.duration,
            resolution=brief.resolution,
            fps=brief.fps,
            aspect=brief.aspect,
            scenes=code_scenes,
            audio=brief.audio,
            output=brief.output
        )
    
    def validate_scene(self, scene: Scene) -> List[str]:
        errors = []
        code_errors = self.code_backend.validate_scene(scene)
        ai_errors = self.ai_backend.validate_scene(scene)
        errors.extend(code_errors)
        errors.extend(ai_errors)
        return errors
    
    def cleanup(self):
        self.code_backend.cleanup()
        self.ai_backend.cleanup()


class HybridPlanner:
    """Decides which elements are code vs AI"""
    
    CODE_CATEGORIES = {
        "camera", "timing", "text", "ui", "data", "charts",
        "geometry", "grid", "lattice", "cursor", "particles",
        "shader", "procedural", "typography", "layout"
    }
    
    AI_CATEGORIES = {
        "nature", "human", "fluid", "smoke", "fire", "organic",
        "character", "face", "skin", "hair", "cloth", "water",
        "clouds", "foliage", "atmosphere", "lighting_complex"
    }
    
    TEXTURE_CATEGORIES = {
        "material", "surface", "texture", "book_cover", "wall",
        "floor", "fabric", "metal", "glass", "wood", "stone"
    }
    
    def plan(self, scene: Scene) -> List[Dict]:
        """Plan element assignments for a scene"""
        
        elements = []
        
        # Always code: camera, timing
        elements.append({
            "id": f"{scene.id}_camera",
            "type": "code",
            "category": "camera",
            "renderer": "ascii"
        })
        
        # Analyze scene description for hints
        desc = scene.description.lower()
        params = scene.parameters
        
        # Check for explicit element list
        if "elements" in params:
            for elem in params["elements"]:
                elements.append(self._classify_element(elem, scene))
        else:
            # Auto-classify based on description
            elements.extend(self._auto_classify(scene))
        
        return elements
    
    def _classify_element(self, elem: Dict, scene: Scene) -> Dict:
        elem_type = elem.get("type", "auto")
        category = elem.get("category", "unknown")
        
        if elem_type == "code" or category in self.CODE_CATEGORIES:
            return {**elem, "type": "code", "renderer": elem.get("renderer", "ascii")}
        elif elem_type == "ai_video" or category in self.AI_CATEGORIES:
            return {**elem, "type": "ai_video", "model": elem.get("model", "veo-3.1")}
        elif elem_type == "ai_texture" or category in self.TEXTURE_CATEGORIES:
            return {**elem, "type": "ai_texture", "model": elem.get("model", "nano-banana")}
        else:
            return {**elem, "type": self._guess_type(category)}
    
    def _auto_classify(self, scene: Scene) -> List[Dict]:
        elements = []
        desc = scene.description.lower()
        
        # Common patterns
        if "library" in desc or "books" in desc:
            elements.append({
                "id": f"{scene.id}_books",
                "type": "ai_texture",
                "category": "material",
                "model": "nano-banana",
                "prompt": "golden leather book spines, aged paper, dust"
            })
        
        if "particle" in desc or "token" in desc or "spiral" in desc:
            elements.append({
                "id": f"{scene.id}_particles",
                "type": "code",
                "category": "particles",
                "renderer": "ascii"
            })
        
        if "human" in desc or "face" in desc or "character" in desc:
            elements.append({
                "id": f"{scene.id}_character",
                "type": "ai_video",
                "category": "human",
                "model": "veo-3.1"
            })
        
        if "water" in desc or "ocean" in desc or "sea" in desc:
            elements.append({
                "id": f"{scene.id}_water",
                "type": "ai_video",
                "category": "fluid",
                "model": "veo-3.1"
            })
        
        return elements
    
    def _guess_type(self, category: str) -> str:
        if category in self.CODE_CATEGORIES:
            return "code"
        elif category in self.AI_CATEGORIES:
            return "ai_video"
        elif category in self.TEXTURE_CATEGORIES:
            return "ai_texture"
        return "code"  # Default to code


class HybridCompositor:
    """Composites code and AI renders"""
    
    def __init__(self, color_space: str = "acescg", default_blend: str = "over"):
        self.color_space = color_space
        self.default_blend = default_blend
    
    def composite(self, code_frame: Image.Image, 
                 ai_frame: Optional[Image.Image],
                 elements: List[Dict], t: float) -> Image.Image:
        """Composite a single frame"""
        
        # Start with code frame
        base = code_frame.convert("RGBA")
        
        if ai_frame is None:
            return base.convert("RGB")
        
        # Resize AI frame to match
        if ai_frame.size != base.size:
            ai_frame = ai_frame.resize(base.size, Image.LANCZOS)
        
        ai_frame = ai_frame.convert("RGBA")
        
        # Apply blend mode from elements
        blend_mode = self.default_blend
        opacity = 1.0
        
        for elem in elements:
            if elem.get("type") in ["ai_video", "ai_texture"]:
                blend_mode = elem.get("blend_mode", self.default_blend)
                opacity = elem.get("opacity", 1.0)
                break
        
        # Apply blend
        composite = self._blend(base, ai_frame, blend_mode, opacity)
        
        return composite.convert("RGB")
    
    def _blend(self, base: Image.Image, overlay: Image.Image,
              mode: str, opacity: float) -> Image.Image:
        """Blend two RGBA images"""
        
        import numpy as np
        
        base_arr = np.array(base, dtype=np.float32) / 255.0
        overlay_arr = np.array(overlay, dtype=np.float32) / 255.0
        
        if mode == "over":
            # Standard alpha over
            result = base_arr * (1 - overlay_arr[:, :, 3:4] * opacity) + \
                     overlay_arr[:, :, :3] * overlay_arr[:, :, 3:4] * opacity
            alpha = base_arr[:, :, 3:4] + overlay_arr[:, :, 3:4] * opacity * (1 - base_arr[:, :, 3:4])
            result = np.concatenate([result, alpha], axis=2)
            
        elif mode == "multiply":
            result = base_arr * (1 - opacity) + base_arr * overlay_arr * opacity
            
        elif mode == "screen":
            result = base_arr * (1 - opacity) + (1 - (1 - base_arr) * (1 - overlay_arr)) * opacity
            
        elif mode == "add":
            result = np.clip(base_arr + overlay_arr * opacity, 0, 1)
            
        elif mode == "overlay":
            # Overlay blend mode
            mask = base_arr < 0.5
            result = np.where(mask, 2 * base_arr * overlay_arr, 1 - 2 * (1 - base_arr) * (1 - overlay_arr))
            result = base_arr * (1 - opacity) + result * opacity
            
        else:
            result = base_arr
        
        result = np.clip(result * 255, 0, 255).astype(np.uint8)
        return Image.fromarray(result, "RGBA")


class TemporalStabilizer:
    """Stabilizes AI frames temporally"""
    
    def __init__(self):
        self.prev_flow = None
    
    def stabilize(self, frames: List[Image.Image]) -> List[Image.Image]:
        """Apply temporal stabilization to frame sequence"""
        # In production, use optical flow to stabilize
        return frames