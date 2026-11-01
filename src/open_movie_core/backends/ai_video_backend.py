"""
AI Video Backend - Veo, Seedance, Kling, etc. via Hyper MCP
"""

from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import asyncio
import logging
import json
import uuid

from .base import VideoBackend, BackendCapabilities, register_backend
from ..brief import ProjectBrief, Scene

logger = logging.getLogger(__name__)


@register_backend("ai_video")
class AIVideoBackend(VideoBackend):
    """AI Video generation backend using Hyper MCP or direct APIs"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.hyper_url = config.get("hyper_url", "http://localhost:8080")
        self.hyper_api_key = config.get("hyper_api_key")
        self.primary_model = config.get("primary_model", "veo-3.1")
        self.fallback_models = config.get("fallback_models", ["seedance-4.5", "kling-3.0"])
        self.max_concurrent = config.get("max_concurrent", 3)
        self.timeout_per_clip = config.get("timeout_per_clip", 300)
        self.quality_review = config.get("quality_review", True)
        self.auto_regenerate = config.get("auto_regenerate", True)
        self.max_regenerations = config.get("max_regenerations", 3)
        
        # Model configs
        self.model_configs = config.get("models", {
            "veo-3.1": {"max_duration": 60, "resolution": "4K", "aspect_ratios": ["16:9", "9:16"]},
            "gemini-omni": {"max_duration": 10, "resolution": "1080p", "aspect_ratios": ["16:9", "9:16"]},
            "seedance-4.5": {"max_duration": 10, "resolution": "1080p", "aspect_ratios": ["16:9", "9:16"]},
            "kling-3.0": {"max_duration": 10, "resolution": "1080p", "aspect_ratios": ["16:9", "9:16"]},
        })
        
        # Scene chaining state
        self.reference_frames: Dict[str, str] = {}  # scene_id -> file_id of last frame
        self.latent_cache: Dict[str, str] = {}  # scene_id -> latent code
    
    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            max_resolution=(1920, 1080),
            max_fps=30,
            max_duration=60.0,  # per clip
            supports_transparency=False,
            supports_audio=True,
            estimated_fps=0.5,  # clips per minute
            deterministic=False,
            gpu_required=False,
            cost_per_second=0.50,  # credits per second (varies by model)
            supported_formats=["mp4", "mov"]
        )
    
    def _get_model_config(self, model: str) -> Dict:
        return self.model_configs.get(model, self.model_configs[self.primary_model])
    
    def _build_prompt(self, scene: Scene, model: str) -> str:
        """Build model-specific prompt from scene"""
        
        templates = {
            "veo-3.1": """
{description}
Camera: {camera}
Lighting: {lighting}
Style: Cinematic, 4K, {lens}mm, {aperture}, {film_stock}
Color: {color_grade}
Negative: morphing, warping, melting, jelly motion, slow motion, blurry, low quality, watermark, text, logo, artifacts
""",
            "gemini-omni": """
{description}
{camera}
{lighting}
High quality, detailed, consistent character, {aspect_ratio}
""",
            "seedance-4.5": """
{description}, {camera}, {lighting},
masterpiece, best quality, ultra-detailed, {aspect_ratio}
""",
            "kling-3.0": """
{description}, {camera}, {lighting},
cinematic lighting, 8k, highly detailed, {aspect_ratio}
"""
        }
        
        template = templates.get(model, templates["veo-3.1"])
        
        # Extract camera and lighting from scene
        camera_desc = self._camera_to_prompt(scene.camera) if scene.camera else "static camera"
        lighting_desc = scene.parameters.get("lighting", "natural lighting")
        lens = scene.parameters.get("lens", "35mm")
        aperture = scene.parameters.get("aperture", "f/2.8")
        film_stock = scene.parameters.get("film_stock", "Kodak Vision3 500T")
        color_grade = scene.parameters.get("color_grade", "teal and orange")
        aspect_ratio = scene.parameters.get("aspect_ratio", "9:16")
        
        # Add consistency tokens
        desc = scene.description
        if scene.parameters.get("character_consistency"):
            desc += f", {scene.parameters['character_consistency']}"
        if scene.parameters.get("environment_consistency"):
            desc += f", {scene.parameters['environment_consistency']}"
        
        return template.format(
            description=desc,
            camera=camera_desc,
            lighting=lighting_desc,
            lens=lens,
            aperture=aperture,
            film_stock=film_stock,
            color_grade=color_grade,
            aspect_ratio=aspect_ratio
        ).strip()
    
    def _camera_to_prompt(self, camera) -> str:
        if not camera:
            return "static camera"
        
        if camera.type == "dolly":
            return "slow dolly forward"
        elif camera.type == "orbit":
            return "orbit around subject"
        elif camera.type == "static":
            return "static camera, subtle micro-movements"
        elif camera.keyframes:
            return f"camera moves from {camera.keyframes[0].position} to {camera.keyframes[-1].position}"
        return "cinematic camera movement"
    
    async def _call_hyper(self, tool: str, params: Dict) -> Dict:
        """Call Hyper MCP tool"""
        # This would use the actual Hyper MCP client
        # For now, simulate the interface
        logger.info(f"Calling Hyper MCP: {tool} with {params}")
        
        # Simulated response
        return {"file_id": f"hyper_{uuid.uuid4().hex[:8]}", "status": "completed"}
    
    async def generate_clip(self, scene: Scene, model: str = None) -> Dict:
        """Generate a single video clip for a scene"""
        
        model = model or self.primary_model
        config = self._get_model_config(model)
        
        # Build prompt
        prompt = self._build_prompt(scene, model)
        
        # Get image prompt for chaining (last frame of previous scene)
        image_prompt = None
        if scene.id in self.reference_frames:
            image_prompt = self.reference_frames[scene.id]
        
        # Generation parameters
        gen_params = {
            "prompt": prompt,
            "model": model,
            "duration": min(scene.duration, config["max_duration"]),
            "aspect_ratio": scene.parameters.get("aspect_ratio", "9:16"),
            "resolution": config["resolution"]
        }
        
        if image_prompt:
            gen_params["image_prompt"] = image_prompt
            gen_params["image_prompt_strength"] = 0.8
        
        # Try primary model, then fallbacks
        models_to_try = [model] + self.fallback_models
        last_error = None
        
        for try_model in models_to_try:
            try:
                logger.info(f"Generating clip for {scene.id} with {try_model}")
                
                # Call Hyper MCP
                result = await self._call_hyper("videos_generate", {
                    **gen_params,
                    "model": try_model
                })
                
                file_id = result.get("file_id")
                if not file_id:
                    raise ValueError("No file_id returned")
                
                # Quality review
                if self.quality_review:
                    review = await self._call_hyper("videos_analyze", {
                        "file_id": file_id,
                        "analysis_type": "quality_review"
                    })
                    
                    if not review.get("passes", False):
                        if self.auto_regenerate:
                            logger.warning(f"Quality review failed for {scene.id}: {review}")
                            continue  # Try next model/regenerate
                        else:
                            raise RuntimeError(f"Quality check failed: {review}")
                
                # Store last frame for chaining
                # In real implementation, extract last frame
                self.reference_frames[scene.id] = file_id
                
                return {
                    "file_id": file_id,
                    "model": try_model,
                    "prompt": prompt,
                    "duration": gen_params["duration"]
                }
                
            except Exception as e:
                last_error = e
                logger.warning(f"Model {try_model} failed: {e}")
                continue
        
        raise RuntimeError(f"All models failed. Last error: {last_error}")
    
    def render_frame(self, scene: Scene, t: float, frame_idx: int) -> Any:
        """Not used for AI backend - use render_full"""
        raise NotImplementedError("AI backend uses render_full")
    
    async def render_full(self, brief: ProjectBrief,
                         progress_callback: Callable[[int, int], None] = None) -> str:
        """Render complete video by generating clips for each scene"""
        
        total_scenes = len(brief.scenes)
        clips = []
        
        for i, scene in enumerate(brief.scenes):
            if progress_callback:
                progress_callback(i, total_scenes)
            
            logger.info(f"Generating scene {i+1}/{total_scenes}: {scene.id}")
            
            clip = await self.generate_clip(scene)
            clips.append(clip)
            
            # Small delay between generations
            await asyncio.sleep(1)
        
        # Stitch clips
        if progress_callback:
            progress_callback(total_scenes, total_scenes)
        
        logger.info("Stitching clips...")
        stitched = await self._call_hyper("videos_stitch", {
            "file_ids": [c["file_id"] for c in clips],
            "transition": "cut"  # Could be per-scene
        })
        
        stitched_id = stitched.get("file_id")
        
        # Download final video
        output_path = self.work_dir / f"{brief.project_id}_ai.mp4"
        await self._download_video(stitched_id, output_path)
        
        return str(output_path)
    
    async def _download_video(self, file_id: str, output_path: Path):
        """Download video from Hyper/storage"""
        # In real implementation, download from Hyper CDN
        logger.info(f"Downloading {file_id} to {output_path}")
        # Simulate download
        output_path.write_bytes(b"fake video data")
    
    def validate_scene(self, scene: Scene) -> List[str]:
        errors = []
        if scene.duration > 60:
            errors.append(f"Scene {scene.id} duration ({scene.duration}s) exceeds max clip duration (60s)")
        return errors
    
    def cleanup(self):
        self.reference_frames.clear()
        self.latent_cache.clear()