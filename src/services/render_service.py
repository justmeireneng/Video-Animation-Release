from __future__ import annotations

import shutil
import subprocess
import json
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
        try:
            output_relative_to_project = output.resolve().relative_to(self.repo_root / "projects" / project_name)
        except ValueError as exc:
            raise ValueError("Render output must stay inside its project directory.") from exc
        relative_output = Path("..") / "projects" / project_name / output_relative_to_project
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

    @property
    def manifest_path(self) -> Path:
        return self.project_root / "project.json"

    def _is_desktop_project(self) -> bool:
        return self.manifest_path.is_file()

    def _preflight(self, *, final: bool) -> dict:
        """Validate creator approval gates for a new local studio project.

        Legacy projects retain their existing render path.  New projects are
        intentionally stricter: no unattended render may skip source review,
        script approval, voice approval, or generated narration audio.
        """

        if not self._is_desktop_project():
            return {}
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        remotion = json.loads((self.project_root / "remotion.json").read_text(encoding="utf-8"))
        missing: list[str] = []
        if not manifest.get("script", {}).get("approved"):
            missing.append("script mapping approval")
        if not manifest.get("voice", {}).get("approved"):
            missing.append("voice approval")
        for scene in remotion.get("scenes", []):
            scene_id = str(scene.get("id", "unknown"))
            metadata_path = self.project_root / "scenes" / scene_id / "metadata.json"
            if not metadata_path.is_file() or not json.loads(metadata_path.read_text(encoding="utf-8")).get("approved_version"):
                missing.append(f"approved video for {scene_id}")
            if not str(scene.get("narration", "")).strip():
                missing.append(f"script for {scene_id}")
            audio = self.project_root / str(scene.get("narrationAudio", ""))
            if not audio.is_file():
                missing.append(f"narration audio for {scene_id}")
        render = manifest.get("render", {})
        if final and not render.get("preview_approved"):
            missing.append("preview approval before final render")
        if missing:
            raise RuntimeError("Render is blocked until: " + "; ".join(missing))
        return manifest

    def approve_preview(self) -> dict:
        """Record the creator's review decision before a full final render."""

        if not self._is_desktop_project():
            return self.state.set("APPROVED", "legacy preview approved")
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        preview = self.project_root / "render" / "preview" / "preview.mp4"
        if not preview.is_file():
            raise RuntimeError("Render and review a preview before approving final render.")
        manifest["render"] = {**dict(manifest.get("render") or {}), "preview_ready": True, "preview_approved": True}
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.state.set("READY_TO_RENDER", "preview approved by creator")
        return manifest

    def render_preview(self) -> Path:
        self._preflight(final=False)
        output = self.project_root / ("render/preview/preview.mp4" if self._is_desktop_project() else "output/preview.mp4")
        self.state.set("RENDERING", "preview")
        try:
            self.renderer.render(self.project_name, output, preview=True)
        except Exception:
            self.state.set("NEEDS_CHANGES", "preview render failed")
            raise
        if self._is_desktop_project():
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            manifest["render"] = {**dict(manifest.get("render") or {}), "preview_ready": True, "preview_approved": False}
            self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.state.set("POST_RENDER_REVIEW", "preview ready for creator review")
        else:
            self.state.set("REVIEW", "preview ready")
        return output

    def render_final(self) -> Path:
        self._preflight(final=True)
        if self._is_desktop_project():
            intermediate = self.project_root / "render" / "final" / "final_remotion.mp4"
            output = self.project_root / "render" / "final" / "final.mp4"
        else:
            intermediate = self.project_root / "output" / "final_remotion.mp4"
            output = self.project_root / "output" / "final.mp4"
        self.state.set("RENDERING", "final")
        try:
            self.renderer.render(self.project_name, intermediate, preview=False)
            self.finalizer.finalize(intermediate, output)
        except Exception:
            self.state.set("NEEDS_CHANGES", "final render failed")
            raise
        if self._is_desktop_project():
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            manifest["render"] = {**dict(manifest.get("render") or {}), "final_ready": True}
            self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.state.set("POST_RENDER_REVIEW", "final ready for creator review")
        else:
            self.state.set("REVIEW", "final ready")
        return output
