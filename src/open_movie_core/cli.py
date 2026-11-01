#!/usr/bin/env python3
"""
OPEN MOVIE CLI - Universal Video Generation Pipeline

Usage:
    om init --brief project.yaml
    om render --brief project.yaml --output video.mp4
    om render --brief project.yaml --backend hybrid --output video.mp4
    om validate --brief project.yaml
    om doctor
    om backends
    om scene --brief project.yaml --scene void --output void.mp4
"""

import argparse
import asyncio
import sys
import logging
from pathlib import Path
from typing import Optional

from .brief import ProjectBrief
from .pipeline import OpenMoviePipeline, PipelineConfig, render_sync
from .backends.base import BackendRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("openmovie")


def setup_logging(level: str = "INFO"):
    logging.getLogger().setLevel(getattr(logging, level.upper()))


def cmd_init(args):
    """Initialize a new project"""
    brief_path = Path(args.brief)
    
    if brief_path.exists() and not args.force:
        print(f"Error: {brief_path} already exists. Use --force to overwrite.")
        return 1
    
    # Create template brief
    template = """project:
  id: "om-new-project"
  title: "New Video Project"
  duration: 60
  resolution: "1080x1920"
  fps: 30
  aspect: "9:16"

pipeline:
  backend: "auto"
  quality: "high"

scenes:
  - id: "intro"
    start: 0
    end: 10
    description: "Opening scene"
    parameters: {}

  - id: "main"
    start: 10
    end: 50
    description: "Main content"
    parameters: {}

  - id: "outro"
    start: 50
    end: 60
    description: "Closing scene"
    parameters: {}

audio:
  style: "ambient"
  bpm: 60
  key: "Am"
  progression: ["Am9", "Fmaj7", "Dm9", "Em7"]
  loudnorm_target: -16
  generator: "procedural"

output:
  format: "mp4"
  codec: "libx264"
  crf: 18
  preset: "slow"
  pix_fmt: "yuv420p"
  audio_codec: "aac"
  audio_bitrate: "192k"
"""
    
    brief_path.write_text(template)
    print(f"Created project brief: {brief_path}")
    print("Edit the file to define your scenes, then run:")
    print(f"  om render --brief {brief_path} --output output.mp4")
    return 0


def cmd_validate(args):
    """Validate project brief"""
    brief_path = Path(args.brief)
    
    if not brief_path.exists():
        print(f"Error: {brief_path} not found")
        return 1
    
    try:
        brief = ProjectBrief.from_yaml(str(brief_path))
        errors = brief.validate()
        
        if errors:
            print("Validation failed:")
            for err in errors:
                print(f"  ✗ {err}")
            return 1
        else:
            print("✓ Brief is valid")
            print(f"  Project: {brief.title} ({brief.project_id})")
            print(f"  Duration: {brief.duration}s")
            print(f"  Resolution: {brief.resolution}@{brief.fps}fps")
            print(f"  Scenes: {len(brief.scenes)}")
            print(f"  Aspect: {brief.aspect}")
            return 0
    except Exception as e:
        print(f"Error loading brief: {e}")
        return 1


def cmd_render(args):
    """Render video from brief"""
    brief_path = Path(args.brief)
    output_path = Path(args.output)
    
    if not brief_path.exists():
        print(f"Error: {brief_path} not found")
        return 1
    
    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load brief
    try:
        brief = ProjectBrief.from_yaml(str(brief_path))
        errors = brief.validate()
        if errors:
            print("Brief validation failed:")
            for err in errors:
                print(f"  ✗ {err}")
            return 1
    except Exception as e:
        print(f"Error loading brief: {e}")
        return 1
    
    # Setup config
    config = PipelineConfig(
        work_dir=Path(args.work_dir) if args.work_dir else Path("./work"),
        cache_dir=Path(args.cache_dir) if args.cache_dir else Path("./cache"),
        max_parallel_frames=args.parallel,
        frame_timeout=args.timeout,
        checkpoint_interval=args.checkpoint,
        resume=args.resume,
        dry_run=args.dry_run,
        log_level=args.log_level,
        backend_configs={
            "ascii": {
                "chrome_path": args.chrome_path,
                "work_dir": str(config.work_dir / "ascii"),
            },
            "ai_video": {
                "hyper_url": args.hyper_url,
                "primary_model": args.model,
            } if args.hyper_url else {},
            "hybrid": {}
        }
    )
    
    # Backend configs
    if args.chrome_path:
        config.backend_configs.setdefault("ascii", {})["chrome_path"] = args.chrome_path
    
    print(f"Rendering: {brief.title}")
    print(f"  Backend: {args.backend}")
    print(f"  Duration: {brief.duration}s ({int(brief.duration * brief.fps)} frames)")
    print(f"  Output: {output_path}")
    
    if args.dry_run:
        print("DRY RUN - not actually rendering")
        return 0
    
    # Progress callback
    def progress_cb(frame: int, total: int):
        pct = (frame / total * 100) if total > 0 else 0
        print(f"\r  Progress: {frame}/{total} ({pct:.1f}%)", end="", flush=True)
    
    try:
        # Run render
        pipeline = OpenMoviePipeline(config=config, backend=args.backend)
        pipeline.set_progress_callback(progress_cb)
        
        output_file = asyncio.run(pipeline.render(brief, str(output_path)))
        
        print(f"\n✓ Render complete: {output_file}")
        
        # Show file info
        size_mb = Path(output_file).stat().st_size / 1024 / 1024
        print(f"  Size: {size_mb:.1f} MB")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nRender cancelled by user")
        return 130
    except Exception as e:
        print(f"\n✗ Render failed: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def cmd_scene(args):
    """Render a single scene"""
    brief_path = Path(args.brief)
    output_path = Path(args.output)
    
    if not brief_path.exists():
        print(f"Error: {brief_path} not found")
        return 1
    
    brief = ProjectBrief.from_yaml(str(brief_path))
    
    scene = next((s for s in brief.scenes if s.id == args.scene), None)
    if not scene:
        print(f"Error: Scene '{args.scene}' not found. Available: {[s.id for s in brief.scenes]}")
        return 1
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    config = PipelineConfig(
        work_dir=Path(args.work_dir) if args.work_dir else Path("./work"),
        log_level=args.log_level,
    )
    
    print(f"Rendering scene: {scene.id} ({scene.duration}s)")
    
    def progress_cb(frame: int, total: int):
        pct = (frame / total * 100) if total > 0 else 0
        print(f"\r  Progress: {frame}/{total} ({pct:.1f}%)", end="", flush=True)
    
    try:
        pipeline = OpenMoviePipeline(config=config, backend=args.backend)
        pipeline.set_progress_callback(progress_cb)
        
        output_file = pipeline.render_scene(brief, args.scene, str(output_path))
        
        print(f"\n✓ Scene rendered: {output_file}")
        return 0
        
    except Exception as e:
        print(f"\n✗ Scene render failed: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def cmd_doctor(args):
    """Check environment and dependencies"""
    print("OPEN MOVIE Environment Check")
    print("=" * 40)
    
    checks = []
    
    # Python
    checks.append(("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", True))
    
    # FFmpeg
    try:
        import subprocess
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            checks.append(("FFmpeg", version, True))
        else:
            checks.append(("FFmpeg", "Not found", False))
    except:
        checks.append(("FFmpeg", "Not found", False))
    
    # FFprobe
    try:
        result = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            checks.append(("FFprobe", "Available", True))
        else:
            checks.append(("FFprobe", "Not found", False))
    except:
        checks.append(("FFprobe", "Not found", False))
    
    # Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            checks.append(("Node.js", result.stdout.strip(), True))
        else:
            checks.append(("Node.js", "Not found", False))
    except:
        checks.append(("Node.js", "Not found", False))
    
    # Chrome
    chrome_paths = [
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        "/usr/bin/google-chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    chrome_found = False
    for p in chrome_paths:
        if Path(p).exists():
            checks.append(("Chrome", p, True))
            chrome_found = True
            break
    if not chrome_found:
        checks.append(("Chrome", "Not found in standard locations", False))
    
    # Python packages
    packages = ["numpy", "scipy", "yaml", "PIL"]
    for pkg in packages:
        try:
            __import__(pkg)
            checks.append((f"Python:{pkg}", "OK", True))
        except ImportError:
            checks.append((f"Python:{pkg}", "Missing", False))
    
    # Print results
    all_ok = True
    for name, status, ok in checks:
        icon = "✓" if ok else "✗"
        print(f"  {icon} {name}: {status}")
        if not ok:
            all_ok = False
    
    print()
    if all_ok:
        print("All checks passed!")
        return 0
    else:
        print("Some checks failed. Install missing dependencies.")
        return 1


def cmd_backends(args):
    """List available backends"""
    print("Available Backends:")
    print("=" * 40)
    
    for name in BackendRegistry.list():
        backend_class = BackendRegistry.get(name)
        if backend_class:
            # Create temporary instance to get capabilities
            try:
                instance = backend_class({})
                caps = instance.get_capabilities()
                print(f"\n  {name}")
                print(f"    Max Resolution: {caps.max_resolution[0]}x{caps.max_resolution[1]}")
                print(f"    Max FPS: {caps.max_fps}")
                print(f"    Max Duration: {caps.max_duration}s")
                print(f"    Deterministic: {caps.deterministic}")
                print(f"    GPU Required: {caps.gpu_required}")
                print(f"    Est. Speed: {caps.estimated_fps:.1f} fps")
                print(f"    Cost/sec: {caps.cost_per_second}")
            except:
                print(f"\n  {name} (error loading)")
            finally:
                instance.cleanup()
    
    return 0


def cmd_audio(args):
    """Generate audio only"""
    brief_path = Path(args.brief)
    output_path = Path(args.output)
    
    if not brief_path.exists():
        print(f"Error: {brief_path} not found")
        return 1
    
    brief = ProjectBrief.from_yaml(str(brief_path))
    
    from .audio.generator import create_audio_generator
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Generating audio: {brief.title}")
    print(f"  Style: {brief.audio.style}")
    print(f"  Duration: {brief.duration}s")
    print(f"  Output: {output_path}")
    
    try:
        generator = create_audio_generator(brief)
        audio_path = asyncio.run(generator.generate(brief))
        
        # Move to output
        import shutil
        shutil.move(audio_path, output_path)
        
        print(f"✓ Audio generated: {output_path}")
        return 0
    except Exception as e:
        print(f"✗ Audio generation failed: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        prog="om",
        description="OPEN MOVIE - Universal Video Generation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  om init --brief project.yaml                    # Create new project template
  om validate --brief project.yaml                # Validate project brief
  om render --brief project.yaml --output out.mp4 # Render video
  om render --brief project.yaml --backend hybrid # Use hybrid backend
  om scene --brief project.yaml --scene intro     # Render single scene
  om doctor                                       # Check environment
  om backends                                     # List backends
  om audio --brief project.yaml --output score.wav # Generate audio only
"""
    )
    
    parser.add_argument("--log-level", default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--debug", action="store_true", help="Show full tracebacks")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # init
    p_init = subparsers.add_parser("init", help="Initialize new project")
    p_init.add_argument("--brief", required=True, help="Path to project brief YAML")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing")
    
    # validate
    p_val = subparsers.add_parser("validate", help="Validate project brief")
    p_val.add_argument("--brief", required=True, help="Path to project brief YAML")
    
    # render
    p_render = subparsers.add_parser("render", help="Render video from brief")
    p_render.add_argument("--brief", required=True, help="Path to project brief YAML")
    p_render.add_argument("--output", "-o", required=True, help="Output video path")
    p_render.add_argument("--backend", default="auto", 
                         choices=["auto", "ascii", "ai_video", "hybrid"])
    p_render.add_argument("--work-dir", help="Working directory")
    p_render.add_argument("--cache-dir", help="Cache directory")
    p_render.add_argument("--parallel", type=int, default=4, help="Parallel frames")
    p_render.add_argument("--timeout", type=int, default=300, help="Frame timeout (s)")
    p_render.add_argument("--checkpoint", type=int, default=100, help="Checkpoint interval")
    p_render.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    p_render.add_argument("--dry-run", action="store_true", help="Validate only")
    p_render.add_argument("--chrome-path", help="Chrome executable path")
    p_render.add_argument("--hyper-url", help="Hyper MCP URL for AI backend")
    p_render.add_argument("--model", default="veo-3.1", help="AI model to use")
    
    # scene
    p_scene = subparsers.add_parser("scene", help="Render single scene")
    p_scene.add_argument("--brief", required=True, help="Path to project brief YAML")
    p_scene.add_argument("--scene", required=True, help="Scene ID to render")
    p_scene.add_argument("--output", "-o", required=True, help="Output video path")
    p_scene.add_argument("--backend", default="auto", choices=["auto", "ascii", "ai_video", "hybrid"])
    p_scene.add_argument("--work-dir", help="Working directory")
    
    # doctor
    p_doctor = subparsers.add_parser("doctor", help="Check environment")
    
    # backends
    p_backends = subparsers.add_parser("backends", help="List available backends")
    
    # audio
    p_audio = subparsers.add_parser("audio", help="Generate audio only")
    p_audio.add_argument("--brief", required=True, help="Path to project brief YAML")
    p_audio.add_argument("--output", "-o", required=True, help="Output audio path")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    setup_logging(args.log_level)
    
    commands = {
        "init": cmd_init,
        "validate": cmd_validate,
        "render": cmd_render,
        "scene": cmd_scene,
        "doctor": cmd_doctor,
        "backends": cmd_backends,
        "audio": cmd_audio,
    }
    
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())