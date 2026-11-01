"""
ASCII Backend - Three.js + ASCII Shader Rendering
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import json
import subprocess
import tempfile
import shutil
import logging
import asyncio

from .base import VideoBackend, BackendCapabilities, register_backend
from ..brief import ProjectBrief, Scene

logger = logging.getLogger(__name__)


@register_backend("ascii")
class ASCIIBackend(VideoBackend):
    """Three.js + ASCII shader backend for deterministic terminal-style videos"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.chrome_path = config.get("chrome_path", 
            "C:/Program Files/Google/Chrome/Application/chrome.exe")
        self.film_template = config.get("film_template", 
            Path(__file__).parent.parent.parent.parent / "skills" / "open-movie-ascii" / "src" / "film.html.j2")
        self.render_script = config.get("render_script",
            Path(__file__).parent.parent.parent.parent / "skills" / "open-movie-ascii" / "render" / "render.js")
        self.node_path = config.get("node_path", "node")
        
        # Verify dependencies
        self._verify_dependencies()
    
    def _verify_dependencies(self):
        """Check that required tools are available"""
        # Check Node.js
        try:
            subprocess.run([self.node_path, "--version"], capture_output=True, check=True)
        except:
            logger.warning("Node.js not found - ASCII backend may not work")
        
        # Check Chrome
        if not Path(self.chrome_path).exists():
            logger.warning(f"Chrome not found at {self.chrome_path}")
    
    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            max_resolution=(1080, 1920),
            max_fps=30,
            max_duration=600.0,
            supports_transparency=False,
            supports_audio=True,
            estimated_fps=8.0,
            deterministic=True,
            gpu_required=True,
            cost_per_second=0.0,
            supported_formats=["mp4", "webm"]
        )
    
    def render_frame(self, scene: Scene, t: float, frame_idx: int) -> Path:
        """Render single frame via Puppeteer (slow for single frames, use render_segment)"""
        # This is not efficient for single frames - use render_segment instead
        raise NotImplementedError("Use render_segment for ASCII backend")
    
    def render_segment(self, scene: Scene, start_frame: int, 
                      end_frame: int) -> List[Path]:
        """Render frame range by generating scene HTML and running Puppeteer"""
        
        # Generate film.html for this scene
        film_html = self._generate_film_html(scene)
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(film_html)
            film_path = f.name
        
        try:
            # Run Puppeteer renderer
            frames = self._run_puppeteer_render(
                film_path, scene, start_frame, end_frame
            )
            return frames
        finally:
            Path(film_path).unlink(missing_ok=True)
    
    def _generate_film_html(self, scene: Scene) -> str:
        """Generate film.html from template with scene parameters"""
        # For now, return a minimal template - in production use Jinja2
        template = self._get_default_template()
        
        # Inject scene-specific parameters
        params = {
            "SCENE_ID": scene.id,
            "SCENE_START": scene.start,
            "SCENE_END": scene.end,
            "DURATION": scene.duration,
            "FPS": self.config.get("fps", 30),
            "WIDTH": self.config.get("width", 1080),
            "HEIGHT": self.config.get("height", 1920),
            "CAMERA_PARAMS": json.dumps(self._compute_camera_params(scene)),
            "SCENE_PARAMS": json.dumps(scene.parameters)
        }
        
        for key, value in params.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))
        
        return template
    
    def _get_default_template(self) -> str:
        """Get minimal film.html template"""
        # This would normally load from film.html.j2
        # Returning a minimal version for the backend
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>OPEN MOVIE - {{SCENE_ID}}</title>
    <style>
        body { margin: 0; overflow: hidden; background: #000; }
        canvas { display: block; }
    </style>
</head>
<body>
    <script src="https://unpkg.com/three@0.149.0/build/three.min.js"></script>
    <script>
        // Scene parameters injected here
        const SCENE_PARAMS = {{SCENE_PARAMS}};
        const CAMERA_PARAMS = {{CAMERA_PARAMS}};
        
        // Three.js scene setup
        const W = {{WIDTH}}, H = {{HEIGHT}};
        const renderer = new THREE.WebGLRenderer({antialias: false});
        renderer.setSize(W, H);
        document.body.appendChild(renderer.domElement);
        
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(58, W/H, 0.08, 800);
        
        // Build scene based on SCENE_PARAMS
        buildScene(scene, SCENE_PARAMS);
        
        // ASCII post-processing
        const composer = new ASCIIComposer(renderer, scene, camera);
        
        // Render function for Puppeteer
        window.__render = function(t) {
            updateCamera(t);
            composer.render(t);
        };
        window.__ready = true;
    </script>
</body>
</html>
"""
    
    def _compute_camera_params(self, scene: Scene) -> Dict:
        """Compute camera keyframes for scene"""
        if scene.camera and scene.camera.keyframes:
            return {
                "type": scene.camera.type,
                "keyframes": [
                    {"time": kf.time, "position": kf.position, "target": kf.target}
                    for kf in scene.camera.keyframes
                ]
            }
        # Default dolly
        return {
            "type": "dolly",
            "start_z": 16,
            "end_z": -414,
            "duration": scene.duration
        }
    
    def _run_puppeteer_render(self, film_path: str, scene: Scene,
                             start_frame: int, end_frame: int) -> List[Path]:
        """Run Puppeteer to render frames"""
        
        frame_dir = self.work_dir / "frames" / scene.id
        frame_dir.mkdir(parents=True, exist_ok=True)
        
        # Create render script
        script = f"""
const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME = '{self.chrome_path.replace("\\", "\\\\")}';
const FILM = '{film_path.replace("\\", "\\\\")}';
const OUT_DIR = '{str(frame_dir).replace("\\", "\\\\")}';
const START = {start_frame};
const END = {end_frame};
const FPS = {self.config.get("fps", 30)};

(async () => {{
    const browser = await puppeteer.launch({{
        executablePath: CHROME,
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--hide-scrollbars', 
               '--mute-audio', '--ignore-gpu-blocklist', '--use-angle=d3d11'],
        defaultViewport: {{ width: {self.config.get("width", 1080)}, 
                           height: {self.config.get("height", 1920)}, 
                           deviceScaleFactor: 1 }}
    }});
    
    const page = await browser.newPage();
    await page.goto('file:///' + FILM.replace(/\\\\/g, '/'), {{ waitUntil: 'load', timeout: 60000 }});
    await page.waitForFunction('window.__ready === true', {{ timeout: 60000 }});
    
    // Warmup
    await page.evaluate(t => window.__render(t), START / FPS);
    await new Promise(r => setTimeout(r, 200));
    
    for (let f = START; f <= END; f++) {{
        const t = f / FPS;
        await page.evaluate(t => window.__render(t), t);
        
        const framePath = path.join(OUT_DIR, `frame_${{String(f).padStart(5, '0')}}.jpg`);
        await page.screenshot({{ path: framePath, type: 'jpeg', quality: 92 }});
    }}
    
    await browser.close();
    console.log('DONE');
}})().catch(e => {{ console.error(e); process.exit(1); }});
"""
        
        script_path = frame_dir / "render_scene.js"
        script_path.write_text(script)
        
        # Run Node.js
        result = subprocess.run(
            [self.node_path, str(script_path)],
            capture_output=True,
            text=True,
            timeout=self.config.get("frame_timeout", 300) * (end_frame - start_frame + 1)
        )
        
        if result.returncode != 0:
            logger.error(f"Puppeteer render failed: {result.stderr}")
            raise RuntimeError(f"Render failed: {result.stderr}")
        
        # Collect frame paths
        frames = []
        for i in range(start_frame, end_frame + 1):
            frame_path = frame_dir / f"frame_{i:05d}.jpg"
            if frame_path.exists():
                frames.append(frame_path)
            else:
                logger.warning(f"Missing frame: {frame_path}")
        
        return frames
    
    async def render_full(self, brief: ProjectBrief,
                         progress_callback: Callable[[int, int], None] = None) -> str:
        """Render complete video using the main render.js script"""
        
        # Generate full film.html with all scenes
        film_html = self._generate_full_film_html(brief)
        
        film_path = self.work_dir / "film.html"
        film_path.write_text(film_html)
        
        # Run main render script
        output_path = self.work_dir / f"{brief.project_id}.mp4"
        
        # Use the existing render.js if available
        if Path(self.render_script).exists():
            cmd = [
                self.node_path, str(self.render_script),
                "0", str(int(brief.duration * brief.fps) - 1),
                brief.project_id
            ]
            
            # Set environment for film.html location
            env = {**os.environ, "FILM_PATH": str(film_path)}
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise RuntimeError(f"Render failed: {stderr.decode()}")
            
            # Find output
            if output_path.exists():
                return str(output_path)
        
        # Fallback: frame-by-frame then encode
        raise NotImplementedError("Full render needs render.js integration")
    
    def _generate_full_film_html(self, brief: ProjectBrief) -> str:
        """Generate complete film.html with all scenes"""
        # This would use the full Jinja2 template from the ascii skill
        # For now, return placeholder
        return f"<!-- Full film.html for {brief.project_id} -->"
    
    def validate_scene(self, scene: Scene) -> List[str]:
        errors = []
        if scene.duration > self.get_capabilities().max_duration:
            errors.append(f"Scene {scene.id} duration ({scene.duration}s) exceeds max ({self.get_capabilities().max_duration}s)")
        return errors
    
    def cleanup(self):
        """Clean up temp files"""
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir, ignore_errors=True)


# Need to import os
import os