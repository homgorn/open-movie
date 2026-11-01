"""
Backend Base Classes and Registry
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import asyncio
import logging

from ..brief import ProjectBrief, Scene

logger = logging.getLogger(__name__)


@dataclass
class BackendCapabilities:
    """What a backend can do"""
    max_resolution: tuple = (1920, 1080)
    max_fps: int = 30
    max_duration: float = 300.0  # seconds per render
    supports_transparency: bool = False
    supports_audio: bool = True
    estimated_fps: float = 10.0  # Rendering speed (frames/second)
    deterministic: bool = False
    gpu_required: bool = False
    cost_per_second: float = 0.0  # Credits or $ per second of output
    supported_formats: List[str] = None
    
    def __post_init__(self):
        if self.supported_formats is None:
            self.supported_formats = ["mp4", "mov", "webm"]


class VideoBackend(ABC):
    """Abstract base class for video rendering backends"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.work_dir = Path(self.config.get("work_dir", "./work"))
        self.work_dir.mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    def get_capabilities(self) -> BackendCapabilities:
        """Return backend capabilities"""
        pass
    
    @abstractmethod
    def render_frame(self, scene: Scene, t: float, frame_idx: int) -> Any:
        """
        Render a single frame.
        
        Args:
            scene: Scene definition
            t: Time in seconds
            frame_idx: Frame index
            
        Returns:
            Frame data (PIL Image, numpy array, or file path)
        """
        pass
    
    def render_segment(self, scene: Scene, start_frame: int, 
                      end_frame: int) -> List[Any]:
        """
        Render a frame range. Default implementation calls render_frame.
        Override for batch rendering optimization.
        """
        frames = []
        for i in range(start_frame, end_frame + 1):
            t = i / self.config.get("fps", 30)
            frames.append(self.render_frame(scene, t, i))
        return frames
    
    async def render_full(self, brief: ProjectBrief, 
                         progress_callback: Callable[[int, int], None] = None) -> str:
        """
        Render complete video. Default raises NotImplementedError.
        Backends that can do full render (AI, Hybrid) should override.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support render_full")
    
    def validate_scene(self, scene: Scene) -> List[str]:
        """Validate scene for this backend. Return list of errors."""
        return []
    
    def estimate_frames(self, scene: Scene, fps: int) -> int:
        """Estimate frames for scene"""
        return int(scene.duration * fps)
    
    def cleanup(self):
        """Cleanup resources"""
        pass


class BackendRegistry:
    """Registry of available backends"""
    
    _backends: Dict[str, type] = {}
    _instances: Dict[str, VideoBackend] = {}
    
    @classmethod
    def register(cls, name: str, backend_class: type):
        """Register a backend class"""
        if not issubclass(backend_class, VideoBackend):
            raise ValueError(f"{backend_class} must inherit from VideoBackend")
        cls._backends[name] = backend_class
        logger.debug(f"Registered backend: {name}")
    
    @classmethod
    def get(cls, name: str) -> Optional[type]:
        """Get backend class by name"""
        return cls._backends.get(name)
    
    @classmethod
    def list(cls) -> List[str]:
        """List registered backend names"""
        return list(cls._backends.keys())
    
    @classmethod
    def create(cls, name: str, config: Dict = None) -> VideoBackend:
        """Create backend instance"""
        if name not in cls._backends:
            raise ValueError(f"Unknown backend: {name}. Available: {cls.list()}")
        
        if name in cls._instances:
            return cls._instances[name]
        
        instance = cls._backends[name](config)
        cls._instances[name] = instance
        return instance
    
    @classmethod
    def clear_instances(cls):
        """Clear cached instances"""
        for instance in cls._instances.values():
            instance.cleanup()
        cls._instances.clear()


# Decorator for easy backend registration
def register_backend(name: str):
    """Decorator to register a backend class"""
    def decorator(cls):
        BackendRegistry.register(name, cls)
        return cls
    return decorator