#!/usr/bin/env python3
import subprocess
from pathlib import Path
from ..base import VideoProvider, VideoGenerationRequest
from core.motion.cinematic_engine import CinematicMotionEngine, MotionConfig, MotionType

class CinematicMotionVideoProvider(VideoProvider):
    def __init__(self, target_w: int = 1080, target_h: int = 1920):
        self.engine = CinematicMotionEngine(target_w, target_h)

    def animate_image(self, request: VideoGenerationRequest) -> Path:
        cfg = MotionConfig(
            duration_s=request.duration_s,
            fps=request.fps,
            light_sweep=True,
            particles=True
        )
        return self.engine.render_clip(request.image_path, request.output_path, cfg)

class GoogleFlowVideoProvider(VideoProvider):
    def __init__(self, auto_import_dir: Path | str = "flow_videos"):
        self.import_dir = Path(auto_import_dir)

    def animate_image(self, request: VideoGenerationRequest) -> Path:
        out_p = Path(request.output_path)
        candidate = self.import_dir / out_p.name
        if candidate.exists():
            import shutil
            shutil.copy2(candidate, out_p)
            return out_p
        # Fallback to Cinematic Motion Engine if cloud video is not yet imported
        fallback = CinematicMotionVideoProvider()
        return fallback.animate_image(request)

class WanVideoProvider(VideoProvider):
    def __init__(self, comfyui_url: str = "http://127.0.0.1:8188"):
        self.url = comfyui_url

    def animate_image(self, request: VideoGenerationRequest) -> Path:
        # Connects to ComfyUI Wan 2.2 workflow when GPU server is online
        raise NotImplementedError("Wan 2.2 requires active CUDA GPU server.")
