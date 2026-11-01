"""Tests for open_movie_core"""

import pytest
from pathlib import Path

from open_movie_core.brief import ProjectBrief, Scene, CameraPath, AudioBrief
from open_movie_core.pipeline import OpenMoviePipeline, PipelineConfig
from open_movie_core.backends.base import VideoBackend, BackendCapabilities, BackendRegistry


class TestProjectBrief:
    """Test ProjectBrief parsing and validation"""

    def test_minimal_brief(self):
        brief = ProjectBrief(
            project_id="test-001",
            title="Test Video",
            duration=10.0,
            scenes=[
                Scene(id="intro", start=0, end=5, description="Opening"),
                Scene(id="outro", start=5, end=10, description="Closing"),
            ]
        )
        errors = brief.validate()
        assert errors == []

    def test_invalid_scene_timing(self):
        brief = ProjectBrief(
            project_id="test-002",
            title="Test",
            duration=10.0,
            scenes=[
                Scene(id="a", start=0, end=5, description="A"),
                Scene(id="b", start=3, end=8, description="B"),  # Overlap
            ]
        )
        errors = brief.validate()
        assert any("overlap" in e.lower() or "start" in e.lower() for e in errors)

    def test_yaml_roundtrip(self, tmp_path):
        brief = ProjectBrief(
            project_id="test-003",
            title="Roundtrip Test",
            duration=30.0,
            scenes=[
                Scene(id="s1", start=0, end=15, description="First"),
                Scene(id="s2", start=15, end=30, description="Second"),
            ]
        )
        yaml_path = tmp_path / "test.yaml"
        brief.to_yaml(str(yaml_path))
        loaded = ProjectBrief.from_yaml(str(yaml_path))
        assert loaded.project_id == brief.project_id
        assert loaded.duration == brief.duration
        assert len(loaded.scenes) == 2


class TestPipelineConfig:
    """Test pipeline configuration"""

    def test_default_config(self):
        config = PipelineConfig()
        assert config.max_parallel_frames == 4
        assert config.frame_timeout == 300
        assert config.checkpoint_interval == 100

    def test_custom_config(self):
        config = PipelineConfig(
            max_parallel_frames=8,
            frame_timeout=600,
            work_dir=Path("./custom_work"),
        )
        assert config.max_parallel_frames == 8
        assert config.frame_timeout == 600


class TestBackendRegistry:
    """Test backend registration and lookup"""

    def test_register_and_get(self):
        class DummyBackend(VideoBackend):
            def get_capabilities(self):
                return BackendCapabilities()
            def render_frame(self, scene, t, frame_idx):
                return None

        BackendRegistry.register("dummy", DummyBackend)
        assert BackendRegistry.get("dummy") == DummyBackend
        assert "dummy" in BackendRegistry.list()

        # Cleanup
        BackendRegistry._backends.pop("dummy", None)

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError):
            BackendRegistry.get("nonexistent")


class TestScene:
    """Test Scene dataclass"""

    def test_duration_property(self):
        scene = Scene(id="test", start=10, end=25, description="Test")
        assert scene.duration == 15.0

    def test_camera_path(self):
        from open_movie_core.brief import CameraKeyframe, CameraPath
        keyframes = [
            CameraKeyframe(time=0, position=[0, 0, 10]),
            CameraKeyframe(time=10, position=[0, 0, -50]),
        ]
        camera = CameraPath(type="dolly", keyframes=keyframes)
        assert len(camera.keyframes) == 2
        assert camera.keyframes[0].position == [0, 0, 10]


class TestAudioBrief:
    """Test AudioBrief"""

    def test_default_audio(self):
        audio = AudioBrief()
        assert audio.style == "ambient"
        assert audio.bpm == 60
        assert audio.key == "Am"
        assert audio.loudnorm_target == -16.0

    def test_custom_progression(self):
        audio = AudioBrief(progression=["C", "Am", "F", "G"])
        assert audio.progression == ["C", "Am", "F", "G"]


# Integration test (requires FFmpeg, Node, Chrome - marked as integration)
@pytest.mark.integration
@pytest.mark.slow
class TestFullPipeline:
    """Integration tests requiring full environment"""

    @pytest.fixture(scope="class")
    def sample_brief(self):
        return ProjectBrief(
            project_id="integration-test",
            title="Integration Test",
            duration=5.0,
            resolution="640x360",
            fps=10,
            scenes=[
                Scene(id="test", start=0, end=5, description="Test scene"),
            ]
        )

    def test_ascii_render_smoke(self, sample_brief):
        """Smoke test ASCII backend (requires Node, Chrome)"""
        config = PipelineConfig(
            work_dir=Path("./work"),
            max_parallel_frames=1,
            frame_timeout=60,
        )
        pipeline = OpenMoviePipeline(config=config, backend="ascii")
        # This would need actual Node/Chrome - skip in CI without them
        pytest.skip("Requires Node.js and Chrome")


# Fixtures
@pytest.fixture
def tmp_path(tmp_path_factory):
    return tmp_path_factory.mktemp("test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])