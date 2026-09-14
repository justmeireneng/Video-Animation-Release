from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from src.services.project_state import ProjectStateService
from src.video.scene_source_manager import find_ffprobe


class RemotionRenderer:
    def __init__(self, repo_root: Path | str):
        self.repo_root = Path(repo_root).resolve()

    def render(self, project_name: str, output: Path, *, preview: bool) -> Path:
        node = shutil.which("node")
        cli = self.repo_root / "remotion" / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
        if not node or not cli.is_file():
            raise FileNotFoundError("Install the Remotion runtime first: pnpm --dir remotion install")
        props = Path("..") / "projects" / project_name / "remotion-props.json"
        relative_output = Path("..") / "projects" / project_name / "output" / output.name
        command = [
            node, str(cli), "render", "src/index.ts",
            "TikTokExplainer", relative_output.as_posix(), f"--props={props.as_posix()}",
            "--codec=h264", f"--crf={30 if preview else 23}", "--concurrency=1" if preview else "--concurrency=25%",
            "--media-cache-size-in-bytes=251658240",
            "--offthreadvideo-cache-size-in-bytes=268435456",
            "--offthreadvideo-video-threads=1",
        ]
        if preview:
            command.append("--scale=0.5")
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(command, cwd=self.repo_root / "remotion", check=True)
        return output


class FFmpegFinalizer:
    def __init__(self, repo_root: Path | str):
        self.repo_root = Path(repo_root).resolve()

    def _ffmpeg(self) -> Path:
        system = shutil.which("ffmpeg")
        if system:
            return Path(system)
        ffprobe = find_ffprobe(self.repo_root)
        candidate = ffprobe.with_name("ffmpeg.exe")
        if not candidate.exists():
            raise FileNotFoundError("ffmpeg not found.")
        return candidate

    def finalize(self, source: Path, output: Path) -> Path:
        subprocess.run([
            str(self._ffmpeg()), "-y", "-loglevel", "error", "-i", str(source),
            "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(output),
        ], check=True)
        return output


class RenderService:
    def __init__(self, repo_root: Path | str, project_name: str):
        self.repo_root = Path(repo_root).resolve()
        self.project_name = project_name
        self.project_root = self.repo_root / "projects" / project_name
        self.state = ProjectStateService(self.project_root)
        self.renderer = RemotionRenderer(self.repo_root)
        self.finalizer = FFmpegFinalizer(self.repo_root)

    def render_preview(self) -> Path:
        output = self.project_root / "output" / "preview.mp4"
        self.state.set("RENDERING", "preview")
        try:
            self.renderer.render(self.project_name, output, preview=True)
        except Exception:
            self.state.set("NEEDS_CHANGES", "preview render failed")
            raise
        self.state.set("REVIEW", "preview ready")
        return output

    def render_final(self) -> Path:
        intermediate = self.project_root / "output" / "final_remotion.mp4"
        output = self.project_root / "output" / "final.mp4"
        self.state.set("RENDERING", "final")
        try:
            self.renderer.render(self.project_name, intermediate, preview=False)
            self.finalizer.finalize(intermediate, output)
        except Exception:
            self.state.set("NEEDS_CHANGES", "final render failed")
            raise
        self.state.set("REVIEW", "final ready")
        return output
