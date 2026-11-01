"""
Project Brief - Declarative video project specification
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml
import json


@dataclass
class CameraKeyframe:
    time: float
    position: List[float]  # [x, y, z]
    target: List[float] = None
    fov: float = None


@dataclass
class CameraPath:
    type: str = "keyframe"  # keyframe | dolly | orbit | static | custom
    keyframes: List[CameraKeyframe] = field(default_factory=list)
    easing: str = "ease-in-out"
    custom_function: str = None  # Python expression for custom paths


@dataclass
class AudioCue:
    time: float
    type: str  # note | chord | sfx | silence
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AudioBrief:
    style: str = "ambient"  # ambient | cinematic | electronic | orchestral | procedural
    bpm: int = 60
    key: str = "Am"
    progression: List[str] = field(default_factory=lambda: ["Am9", "Fmaj7", "Dm9", "Em7"])
    loudnorm_target: float = -16.0  # LUFS
    duration: float = 0.0  # auto-calculated from scenes
    cues: List[AudioCue] = field(default_factory=list)
    generator: str = "procedural"  # procedural | ai | hybrid


@dataclass
class Scene:
    id: str
    start: float
    end: float
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    camera: Optional[CameraPath] = None
    audio: Optional[AudioBrief] = None
    elements: List[Dict[str, Any]] = field(default_factory=list)  # For hybrid planner
    transition: str = "cut"  # cut | crossfade | morph | custom
    backend_hint: str = None  # ascii | ai_video | hybrid | auto
    
    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class OutputSpec:
    format: str = "mp4"
    codec: str = "libx264"
    crf: int = 18
    preset: str = "slow"
    pix_fmt: str = "yuv420p"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    resolution: str = "1080x1920"
    fps: int = 30
    movflags: str = "+faststart"


@dataclass
class ProjectBrief:
    project_id: str
    title: str
    duration: float
    resolution: str = "1080x1920"
    fps: int = 30
    aspect: str = "9:16"
    scenes: List[Scene] = field(default_factory=list)
    audio: AudioBrief = field(default_factory=AudioBrief)
    output: OutputSpec = field(default_factory=OutputSpec)
    pipeline: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_yaml(cls, path: str) -> "ProjectBrief":
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    @classmethod
    def from_json(cls, path: str) -> "ProjectBrief":
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProjectBrief":
        # Parse scenes
        scenes = []
        for s in data.get("scenes", []):
            camera = None
            if s.get("camera"):
                keyframes = [
                    CameraKeyframe(**kf) for kf in s["camera"].get("keyframes", [])
                ]
                camera = CameraPath(
                    type=s["camera"].get("type", "keyframe"),
                    keyframes=keyframes,
                    easing=s["camera"].get("easing", "ease-in-out"),
                    custom_function=s["camera"].get("custom_function")
                )
            
            audio = None
            if s.get("audio"):
                audio = AudioBrief(**s["audio"])
            
            scenes.append(Scene(
                id=s["id"],
                start=s["start"],
                end=s["end"],
                description=s["description"],
                parameters=s.get("parameters", {}),
                camera=camera,
                audio=audio,
                elements=s.get("elements", []),
                transition=s.get("transition", "cut"),
                backend_hint=s.get("backend_hint")
            ))
        
        # Parse audio
        audio_data = data.get("audio", {})
        audio_cues = [
            AudioCue(**c) for c in audio_data.get("cues", [])
        ]
        audio = AudioBrief(
            style=audio_data.get("style", "ambient"),
            bpm=audio_data.get("bpm", 60),
            key=audio_data.get("key", "Am"),
            progression=audio_data.get("progression", ["Am9", "Fmaj7", "Dm9", "Em7"]),
            loudnorm_target=audio_data.get("loudnorm_target", -16.0),
            duration=audio_data.get("duration", 0.0),
            cues=audio_cues,
            generator=audio_data.get("generator", "procedural")
        )
        
        # Parse output
        output_data = data.get("output", {})
        output = OutputSpec(**output_data)
        
        return cls(
            project_id=data.get("project", {}).get("id", "untitled"),
            title=data.get("project", {}).get("title", "Untitled"),
            duration=data.get("project", {}).get("duration", 0.0),
            resolution=data.get("project", {}).get("resolution", "1080x1920"),
            fps=data.get("project", {}).get("fps", 30),
            aspect=data.get("project", {}).get("aspect", "9:16"),
            scenes=scenes,
            audio=audio,
            output=output,
            pipeline=data.get("pipeline", {}),
            metadata=data.get("metadata", {})
        )
    
    def to_dict(self) -> dict:
        return {
            "project": {
                "id": self.project_id,
                "title": self.title,
                "duration": self.duration,
                "resolution": self.resolution,
                "fps": self.fps,
                "aspect": self.aspect
            },
            "scenes": [
                {
                    "id": s.id,
                    "start": s.start,
                    "end": s.end,
                    "description": s.description,
                    "parameters": s.parameters,
                    "camera": {
                        "type": s.camera.type if s.camera else "keyframe",
                        "keyframes": [
                            {"time": kf.time, "position": kf.position, 
                             "target": kf.target, "fov": kf.fov}
                            for kf in (s.camera.keyframes if s.camera else [])
                        ],
                        "easing": s.camera.easing if s.camera else "ease-in-out",
                        "custom_function": s.camera.custom_function if s.camera else None
                    } if s.camera else None,
                    "audio": {
                        "style": s.audio.style,
                        "bpm": s.audio.bpm,
                        "key": s.audio.key,
                        "progression": s.audio.progression,
                        "loudnorm_target": s.audio.loudnorm_target,
                        "duration": s.audio.duration,
                        "cues": [
                            {"time": c.time, "type": c.type, "params": c.params}
                            for c in s.audio.cues
                        ],
                        "generator": s.audio.generator
                    } if s.audio else None,
                    "elements": s.elements,
                    "transition": s.transition,
                    "backend_hint": s.backend_hint
                }
                for s in self.scenes
            ],
            "audio": {
                "style": self.audio.style,
                "bpm": self.audio.bpm,
                "key": self.audio.key,
                "progression": self.audio.progression,
                "loudnorm_target": self.audio.loudnorm_target,
                "duration": self.audio.duration,
                "cues": [
                    {"time": c.time, "type": c.type, "params": c.params}
                    for c in self.audio.cues
                ],
                "generator": self.audio.generator
            },
            "output": {
                "format": self.output.format,
                "codec": self.output.codec,
                "crf": self.output.crf,
                "preset": self.output.preset,
                "pix_fmt": self.output.pix_fmt,
                "audio_codec": self.output.audio_codec,
                "audio_bitrate": self.output.audio_bitrate,
                "resolution": self.output.resolution,
                "fps": self.output.fps,
                "movflags": self.output.movflags
            },
            "pipeline": self.pipeline,
            "metadata": self.metadata
        }
    
    def to_yaml(self, path: str):
        with open(path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
    
    def to_json(self, path: str):
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def validate(self) -> List[str]:
        """Validate brief, return list of errors (empty if valid)"""
        errors = []
        
        if not self.scenes:
            errors.append("At least one scene required")
        
        # Check scene continuity
        for i, scene in enumerate(self.scenes):
            if scene.start < 0:
                errors.append(f"Scene {scene.id}: start time must be >= 0")
            if scene.end <= scene.start:
                errors.append(f"Scene {scene.id}: end must be > start")
            if i > 0 and scene.start != self.scenes[i-1].end:
                errors.append(f"Scene {scene.id}: start ({scene.start}) != previous end ({self.scenes[i-1].end})")
        
        # Check total duration matches
        if self.scenes:
            total = self.scenes[-1].end
            if abs(total - self.duration) > 0.01:
                errors.append(f"Project duration ({self.duration}) != last scene end ({total})")
        
        # Validate resolution
        try:
            w, h = map(int, self.resolution.split('x'))
            if w <= 0 or h <= 0:
                errors.append("Invalid resolution")
        except:
            errors.append("Resolution must be WIDTHxHEIGHT (e.g., 1080x1920)")
        
        # Validate FPS
        if self.fps <= 0 or self.fps > 120:
            errors.append("FPS must be 1-120")
        
        return errors