"""
OPEN MOVIE Core - Universal Video Generation Pipeline

A unified framework for generating videos through multiple backends:
- ASCII/Code-driven (Three.js + shader)
- AI Video (Veo, Seedance, Kling, etc.)
- Hybrid (Code + AI composition)

Usage:
    from open_movie_core import OpenMoviePipeline, ProjectBrief
    
    brief = ProjectBrief.from_yaml("project.yaml")
    pipeline = OpenMoviePipeline(backend="hybrid")
    output = pipeline.render(brief)
"""

from .brief import ProjectBrief, Scene, CameraPath, AudioBrief
from .pipeline import OpenMoviePipeline, PipelineConfig
from .backends.base import VideoBackend, BackendCapabilities, BackendRegistry
from .backends.ascii_backend import ASCIIBackend
from .backends.ai_video_backend import AIVideoBackend
from .backends.hybrid_backend import HybridBackend
from .audio.generator import AudioGenerator, ProceduralAudioGenerator
from .ffmpeg.encoder import FFmpegEncoder
from .cli import main

__version__ = "0.1.0"
__all__ = [
    "ProjectBrief",
    "Scene", 
    "CameraPath",
    "AudioBrief",
    "OpenMoviePipeline",
    "PipelineConfig",
    "VideoBackend",
    "BackendCapabilities",
    "BackendRegistry",
    "ASCIIBackend",
    "AIVideoBackend",
    "HybridBackend",
    "AudioGenerator",
    "ProceduralAudioGenerator",
    "FFmpegEncoder",
    "main",
]

# Backend registry - auto-register available backends
BackendRegistry.register("ascii", ASCIIBackend)
BackendRegistry.register("ai_video", AIVideoBackend)
BackendRegistry.register("hybrid", HybridBackend)