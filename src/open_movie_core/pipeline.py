"""
Main Pipeline Orchestration
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
import asyncio
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from .brief import ProjectBrief, Scene
from .backends.base import VideoBackend, BackendCapabilities, BackendRegistry
from .audio.generator import AudioGenerator, ProceduralAudioGenerator
from .ffmpeg.encoder import FFmpegEncoder, EncodeConfig

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    work_dir: Path = Path("./work")
    cache_dir: Path = Path("./cache")
    max_parallel_frames: int = 4
    frame_timeout: int = 300  # seconds
    checkpoint_interval: int = 100
    resume: bool = False
    dry_run: bool = False
    log_level: str = "INFO"
    
    # Backend config
    backend_configs: Dict[str, Dict] = None
    
    def __post_init__(self):
        self.work_dir = Path(self.work_dir)
        self.cache_dir = Path(self.cache_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.backend_configs is None:
            self.backend_configs = {}


class RenderProgress:
    """Progress tracking for render jobs"""
    
    def __init__(self, total_frames: int):
        self.total_frames = total_frames
        self.current_frame = 0
        self.start_time = time.time()
        self.frame_times: List[float] = []
        self.errors: List[str] = []
    
    def update(self, frame: int):
        self.current_frame = frame
        self.frame_times.append(time.time())
    
    @property
    def progress(self) -> float:
        return self.current_frame / self.total_frames if self.total_frames > 0 else 0.0
    
    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time
    
    @property
    def fps(self) -> float:
        if len(self.frame_times) < 2:
            return 0.0
        return (len(self.frame_times) - 1) / (self.frame_times[-1] - self.frame_times[0])
    
    @property
    def eta(self) -> float:
        if self.fps <= 0:
            return 0.0
        remaining = self.total_frames - self.current_frame
        return remaining / self.fps
    
    def __str__(self):
        return f"Frame {self.current_frame}/{self.total_frames} ({self.progress*100:.1f}%) | {self.fps:.1f} fps | ETA: {self.eta:.0f}s"


class OpenMoviePipeline:
    """
    Main pipeline orchestration class.
    
    Coordinates backend selection, rendering, audio generation, and encoding.
    """
    
    def __init__(self, config: PipelineConfig = None, backend: str = "auto"):
        self.config = config or PipelineConfig()
        self.backend_name = backend
        self.backend: Optional[VideoBackend] = None
        self.audio_generator: Optional[AudioGenerator] = None
        self.encoder: Optional[FFmpegEncoder] = None
        self._progress_callback: Optional[Callable[[int, int], None]] = None
    
    def set_progress_callback(self, callback: Callable[[int, int], None]):
        """Set callback(frame: int, total: int) for progress updates"""
        self._progress_callback = callback
    
    def _init_backend(self, brief: ProjectBrief) -> VideoBackend:
        """Initialize the selected backend"""
        
        # Auto-select backend if needed
        if self.backend_name == "auto":
            self.backend_name = self._select_backend(brief)
        
        logger.info(f"Using backend: {self.backend_name}")
        
        # Get backend class
        backend_class = BackendRegistry.get(self.backend_name)
        if not backend_class:
            raise ValueError(f"Unknown backend: {self.backend_name}. Available: {BackendRegistry.list()}")
        
        # Get backend config
        backend_config = self.config.backend_configs.get(self.backend_name, {})
        
        # Instantiate
        return backend_class(backend_config)
    
    def _select_backend(self, brief: ProjectBrief) -> str:
        """Auto-select best backend based on project brief"""
        
        # Check scene hints
        ai_scenes = sum(1 for s in brief.scenes if s.backend_hint == "ai_video")
        code_scenes = sum(1 for s in brief.scenes if s.backend_hint == "ascii")
        hybrid_scenes = sum(1 for s in brief.scenes if s.backend_hint == "hybrid")
        
        if hybrid_scenes > 0 or (ai_scenes > 0 and code_scenes > 0):
            return "hybrid"
        elif ai_scenes > code_scenes:
            return "ai_video"
        else:
            return "ascii"
    
    def _init_audio(self, brief: ProjectBrief) -> AudioGenerator:
        """Initialize audio generator"""
        if brief.audio.generator == "procedural":
            return ProceduralAudioGenerator()
        elif brief.audio.generator == "ai":
            # TODO: AI audio generator
            return ProceduralAudioGenerator()
        else:
            return ProceduralAudioGenerator()
    
    def _init_encoder(self, brief: ProjectBrief) -> FFmpegEncoder:
        """Initialize FFmpeg encoder"""
        return FFmpegEncoder(EncodeConfig(
            width=int(brief.resolution.split('x')[0]),
            height=int(brief.resolution.split('x')[1]),
            fps=brief.fps,
            codec=brief.output.codec,
            crf=brief.output.crf,
            preset=brief.output.preset,
            pix_fmt=brief.output.pix_fmt,
            audio_codec=brief.output.audio_codec,
            audio_bitrate=brief.output.audio_bitrate,
            movflags=brief.output.movflags
        ))
    
    async def render(self, brief: ProjectBrief, output_path: str) -> str:
        """
        Render complete video from brief.
        
        Args:
            brief: Project brief
            output_path: Output file path
            
        Returns:
            Path to rendered video
        """
        # Validate brief
        errors = brief.validate()
        if errors:
            raise ValueError(f"Invalid brief: {'; '.join(errors)}")
        
        logger.info(f"Starting render: {brief.title} ({brief.duration}s, {brief.resolution}@{brief.fps}fps)")
        
        # Initialize components
        self.backend = self._init_backend(brief)
        self.audio_generator = self._init_audio(brief)
        self.encoder = self._init_encoder(brief)
        
        # Calculate total frames
        total_frames = int(brief.duration * brief.fps)
        progress = RenderProgress(total_frames)
        
        # Check if backend supports full render
        if hasattr(self.backend, 'render_full'):
            # Backend handles everything
            return await self._render_full_backend(brief, output_path, progress)
        else:
            # Frame-by-frame orchestration
            return await self._render_frame_by_frame(brief, output_path, progress)
    
    async def _render_full_backend(self, brief: ProjectBrief, 
                                   output_path: str, progress: RenderProgress) -> str:
        """Backend handles complete render (AI Video, Hybrid)"""
        
        def progress_cb(frame: int, total: int):
            progress.update(frame)
            logger.info(str(progress))
            if self._progress_callback:
                self._progress_callback(frame, total)
        
        # Generate audio first
        logger.info("Generating audio...")
        audio_path = await self.audio_generator.generate(brief)
        
        # Render video
        logger.info("Rendering video...")
        video_path = await self.backend.render_full(brief, progress_callback=progress_cb)
        
        # Encode final output
        logger.info("Encoding final video...")
        await self.encoder.encode(video_path, audio_path, output_path, progress_cb)
        
        return output_path
    
    async def _render_frame_by_frame(self, brief: ProjectBrief,
                                     output_path: str, progress: RenderProgress) -> str:
        """Frame-by-frame rendering (ASCII backend)"""
        
        # Generate audio
        logger.info("Generating audio...")
        audio_path = await self.audio_generator.generate(brief)
        
        # Render frames in segments
        frame_dir = self.config.work_dir / "frames"
        frame_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Rendering {progress.total_frames} frames...")
        
        # Use thread pool for parallel frame rendering
        with ThreadPoolExecutor(max_workers=self.config.max_parallel_frames) as executor:
            # Submit frame rendering tasks
            futures = []
            for scene in brief.scenes:
                scene_frames = int(scene.duration * brief.fps)
                scene_start = int(scene.start * brief.fps)
                
                future = executor.submit(
                    self._render_scene_frames,
                    scene, scene_start, scene_frames, frame_dir, brief
                )
                futures.append(future)
            
            # Wait for completion
            for future in futures:
                future.result()
        
        # Encode frames to video
        logger.info("Encoding frames to video...")
        frame_pattern = str(frame_dir / "frame_%05d.jpg")
        await self.encoder.encode_frames(frame_pattern, audio_path, output_path)
        
        return output_path
    
    def _render_scene_frames(self, scene: Scene, start_frame: int, 
                           frame_count: int, frame_dir: Path, brief: ProjectBrief):
        """Render all frames for a single scene"""
        for i in range(frame_count):
            frame_idx = start_frame + i
            t = frame_idx / brief.fps
            
            # Check checkpoint
            if self.config.resume:
                frame_path = frame_dir / f"frame_{frame_idx:05d}.jpg"
                if frame_path.exists():
                    progress.update(frame_idx + 1)
                    continue
            
            # Render frame
            frame = self.backend.render_frame(scene, t, frame_idx)
            
            # Save frame
            frame_path = frame_dir / f"frame_{frame_idx:05d}.jpg"
            frame.save(frame_path, quality=92)
            
            progress.update(frame_idx + 1)
            if self._progress_callback:
                self._progress_callback(frame_idx + 1, progress.total_frames)
            
            # Checkpoint
            if frame_idx % self.config.checkpoint_interval == 0:
                logger.info(str(progress))
    
    def render_scene(self, brief: ProjectBrief, scene_id: str, 
                     output_path: str) -> str:
        """Render a single scene (sync version)"""
        scene = next((s for s in brief.scenes if s.id == scene_id), None)
        if not scene:
            raise ValueError(f"Scene not found: {scene_id}")
        
        # Create sub-brief with just this scene
        scene_brief = ProjectBrief(
            project_id=brief.project_id,
            title=f"{brief.title} - {scene_id}",
            duration=scene.duration,
            resolution=brief.resolution,
            fps=brief.fps,
            aspect=brief.aspect,
            scenes=[scene],
            audio=brief.audio,
            output=brief.output,
            pipeline=brief.pipeline
        )
        
        return asyncio.run(self.render(scene_brief, output_path))
    
    def validate_brief(self, brief: ProjectBrief) -> List[str]:
        """Validate brief without rendering"""
        return brief.validate()
    
    def estimate_cost(self, brief: ProjectBrief) -> Dict[str, float]:
        """Estimate rendering cost"""
        if self.backend:
            caps = self.backend.get_capabilities()
            total_seconds = brief.duration
            return {
                "estimated_cost": caps.cost_per_second * total_seconds,
                "estimated_time_minutes": total_seconds / (caps.estimated_fps * 60) if caps.estimated_fps > 0 else 0,
                "backend": self.backend_name
            }
        return {"estimated_cost": 0, "estimated_time_minutes": 0, "backend": self.backend_name}


# Sync wrapper for convenience
def render_sync(brief: ProjectBrief, output_path: str, 
                backend: str = "auto", config: PipelineConfig = None) -> str:
    """Synchronous render wrapper"""
    pipeline = OpenMoviePipeline(config=config, backend=backend)
    return asyncio.run(pipeline.render(brief, output_path))