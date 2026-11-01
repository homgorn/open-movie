"""
FFmpeg Encoder Wrapper
"""

from dataclasses import dataclass
from typing import Optional, Callable, List
from pathlib import Path
import asyncio
import subprocess
import logging
import shlex

logger = logging.getLogger(__name__)


@dataclass
class EncodeConfig:
    """FFmpeg encoding configuration"""
    width: int = 1080
    height: int = 1920
    fps: int = 30
    codec: str = "libx264"
    crf: int = 18
    preset: str = "slow"
    pix_fmt: str = "yuv420p"
    profile: str = "high"
    level: str = "4.1"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_channels: int = 2
    audio_sample_rate: int = 48000
    movflags: str = "+faststart"
    threads: int = 0  # auto
    hwaccel: str = "auto"  # auto, nvenc, qsv, vaapi, none


class FFmpegEncoder:
    """Async FFmpeg encoder wrapper"""
    
    def __init__(self, config: EncodeConfig = None, ffmpeg_path: str = "ffmpeg"):
        self.config = config or EncodeConfig()
        self.ffmpeg_path = ffmpeg_path
        self._verify_ffmpeg()
    
    def _verify_ffmpeg(self):
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError("FFmpeg not found")
            logger.debug(f"FFmpeg: {result.stdout.split(chr(10))[0]}")
        except FileNotFoundError:
            raise RuntimeError(f"FFmpeg not found at {self.ffmpeg_path}")
    
    def _build_video_filters(self) -> List[str]:
        """Build video filter chain"""
        filters = []
        
        # Scale if needed (but usually input matches output)
        filters.append(f"scale={self.config.width}:{self.config.height}:force_original_aspect_ratio=decrease,pad={self.config.width}:{self.config.height}:(ow-iw)/2:(oh-ih)/2")
        
        # FPS
        filters.append(f"fps={self.config.fps}")
        
        # Format
        filters.append(f"format={self.config.pix_fmt}")
        
        return filters
    
    def _build_video_args(self) -> List[str]:
        """Build video encoding arguments"""
        args = [
            "-c:v", self.config.codec,
            "-preset", self.config.preset,
            "-crf", str(self.config.crf),
            "-pix_fmt", self.config.pix_fmt,
            "-profile:v", self.config.profile,
            "-level", self.config.level,
        ]
        
        if self.config.threads > 0:
            args.extend(["-threads", str(self.config.threads)])
        
        # Hardware acceleration
        if self.config.hwaccel != "none":
            if self.config.hwaccel == "nvenc" and self.config.codec == "libx264":
                args[args.index("-c:v") + 1] = "h264_nvenc"
            elif self.config.hwaccel == "qsv" and self.config.codec == "libx264":
                args[args.index("-c:v") + 1] = "h264_qsv"
        
        return args
    
    def _build_audio_args(self) -> List[str]:
        """Build audio encoding arguments"""
        return [
            "-c:a", self.config.audio_codec,
            "-b:a", self.config.audio_bitrate,
            "-ac", str(self.config.audio_channels),
            "-ar", str(self.config.audio_sample_rate),
        ]
    
    def _build_output_args(self) -> List[str]:
        """Build output container arguments"""
        args = ["-movflags", self.config.movflags]
        
        if self.config.movflags and "faststart" in self.config.movflags:
            # For MP4, moov atom at start
            pass
        
        return args
    
    async def encode(
        self, 
        video_path: str, 
        audio_path: str, 
        output_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> str:
        """
        Encode video + audio to final output.
        
        Args:
            video_path: Input video file
            audio_path: Input audio file
            output_path: Output file path
            progress_callback: Optional callback(frame, total) - note: frame approx from time
            
        Returns:
            Output path
        """
        
        # Build filter complex for video
        vf = ",".join(self._build_video_filters())
        
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter:v", vf,
            *self._build_video_args(),
            *self._build_audio_args(),
            *self._build_output_args(),
            "-shortest",  # Stop at shortest input
            output_path
        ]
        
        logger.info(f"Encoding: {' '.join(shlex.quote(c) for c in cmd)}")
        
        return await self._run_ffmpeg(cmd, progress_callback, output_path)
    
    async def encode_frames(
        self,
        frame_pattern: str,  # e.g., "frames/frame_%05d.jpg"
        audio_path: str,
        output_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        start_number: int = 0
    ) -> str:
        """
        Encode image sequence + audio to video.
        
        Args:
            frame_pattern: Glob pattern with %05d for frame numbers
            audio_path: Input audio file
            output_path: Output file path
            progress_callback: Optional callback
            start_number: Starting frame number
        """
        
        vf = ",".join(self._build_video_filters())
        
        cmd = [
            self.ffmpeg_path, "-y",
            "-framerate", str(self.config.fps),
            "-start_number", str(start_number),
            "-i", frame_pattern,
            "-i", audio_path,
            "-filter:v", vf,
            *self._build_video_args(),
            *self._build_audio_args(),
            *self._build_output_args(),
            "-shortest",
            output_path
        ]
        
        logger.info(f"Encoding frames: {' '.join(shlex.quote(c) for c in cmd)}")
        
        return await self._run_ffmpeg(cmd, progress_callback, output_path)
    
    async def _run_ffmpeg(
        self, 
        cmd: List[str], 
        progress_callback: Optional[Callable[[int, int], None]],
        output_path: str
    ) -> str:
        """Run FFmpeg with progress monitoring"""
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Monitor stderr for progress
        stderr_lines = []
        
        async def read_stderr():
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                line = line.decode('utf-8', errors='ignore').strip()
                stderr_lines.append(line)
                
                # Parse progress from ffmpeg output
                if progress_callback and "time=" in line:
                    try:
                        # Parse: frame= 1234 fps= 25 q=23.4 size= 1234kB time=00:00:41.13 bitrate= 245.6kbits/s
                        parts = line.split()
                        for part in parts:
                            if part.startswith("time="):
                                time_str = part[5:]
                                h, m, s = time_str.split(":")
                                total_seconds = int(h) * 3600 + int(m) * 60 + float(s)
                                frame = int(total_seconds * self.config.fps)
                                progress_callback(frame, int(self.config.fps * 148))  # Estimate total
                                break
                    except:
                        pass
        
        await asyncio.gather(
            read_stderr(),
            process.wait()
        )
        
        if process.returncode != 0:
            error = "\n".join(stderr_lines[-20:])  # Last 20 lines
            logger.error(f"FFmpeg failed (code {process.returncode}):\n{error}")
            raise RuntimeError(f"FFmpeg encoding failed: {error}")
        
        # Verify output
        out_path = Path(output_path)
        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError(f"Output file not created or empty: {output_path}")
        
        logger.info(f"Encoded: {output_path} ({out_path.stat().st_size / 1024 / 1024:.1f} MB)")
        return str(output_path)
    
    def get_video_info(self, path: str) -> dict:
        """Get video info using ffprobe"""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration,r_frame_rate,bit_rate,codec_name",
            "-of", "csv=p=0",
            path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            return {
                "width": int(parts[0]),
                "height": int(parts[1]),
                "duration": float(parts[2]),
                "fps": eval(parts[3]) if '/' in parts[3] else float(parts[3]),
                "bitrate": int(parts[4]),
                "codec": parts[5]
            }
        return {}
    
    def extract_frames(
        self,
        video_path: str,
        output_dir: str,
        pattern: str = "frame_%04d.jpg",
        fps: Optional[int] = None
    ) -> List[str]:
        """Extract frames from video"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", video_path,
        ]
        
        if fps:
            cmd.extend(["-vf", f"fps={fps}"])
        
        cmd.extend([
            "-q:v", "2",
            str(output_dir / pattern)
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Frame extraction failed: {result.stderr}")
        
        # Return list of extracted frames
        frames = sorted(output_dir.glob(pattern.replace("%04d", "*").replace("%05d", "*")))
        return [str(f) for f in frames]


class FFmpegEncoderSync:
    """Synchronous wrapper for simpler use cases"""
    
    def __init__(self, config: EncodeConfig = None, ffmpeg_path: str = "ffmpeg"):
        self.async_encoder = FFmpegEncoder(config, ffmpeg_path)
    
    def encode(self, video_path: str, audio_path: str, output_path: str) -> str:
        return asyncio.run(self.async_encoder.encode(video_path, audio_path, output_path))
    
    def encode_frames(self, frame_pattern: str, audio_path: str, output_path: str, 
                     start_number: int = 0) -> str:
        return asyncio.run(self.async_encoder.encode_frames(frame_pattern, audio_path, output_path, start_number))
    
    def get_video_info(self, path: str) -> dict:
        return self.async_encoder.get_video_info(path)
    
    def extract_frames(self, video_path: str, output_dir: str, 
                      pattern: str = "frame_%04d.jpg", fps: Optional[int] = None) -> List[str]:
        return self.async_encoder.extract_frames(video_path, output_dir, pattern, fps)