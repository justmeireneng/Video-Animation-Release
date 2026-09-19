from __future__ import annotations

import shutil
import subprocess
import json
from pathlib import Path

from src.services.project_state import ProjectStateService
from src.video.scene_source_manager import find_ffprobe, probe_video


RENDER_PRESETS = {
    "preview": {
        "width": 720, "height": 1280, "fps": 30,
        "video_bitrate": "5M", "min_video_bitrate": 4_000_000, "max_video_bitrate": 6_000_000,
        "max_rate": "6M", "buffer_size": "10M", "x264_preset": "faster",
    },
    "final": {
        "width": 1080, "height": 1920, "fps": 30,
        "video_bitrate": "10M", "min_video_bitrate": 8_000_000, "max_video_bitrate": 16_000_000,
        "max_rate": "12M", "buffer_size": "20M", "x264_preset": "medium",
    },
}


class RemotionRenderer:
    def __init__(self, repo_root: Path | str):
        self.repo_root = Path(repo_root).resolve()

    def render(self, project_name: str, output: Path, *, preview: bool) -> Path:
        node = shutil.which("node")
        cli = self.repo_root / "remotion" / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
        if not node or not cli.is_file():
            raise FileNotFoundError("Install the Remotion runtime first: pnpm --dir remotion install")
        project_root = self.repo_root / "projects" / project_name
        props_name = "render/render-props.json" if (project_root / "render" / "render-props.json").is_file() else "remotion-props.json"
        props = Path("..") / "projects" / project_name / props_name
        try:
            output_relative_to_project = output.resolve().relative_to(self.repo_root / "projects" / project_name)
        except ValueError as exc:
            raise ValueError("Render output must stay inside its project directory.") from exc
        relative_output = Path("..") / "projects" / project_name / output_relative_to_project
        preset = RENDER_PRESETS["preview" if preview else "final"]
        command = [
            node, str(cli), "render", "src/index.ts",
            "TikTokExplainer", relative_output.as_posix(), f"--props={props.as_posix()}",
            "--codec=h264", "--audio-codec=aac", "--audio-bitrate=192k", "--pixel-format=yuv420p",
            f"--width={preset['width']}", f"--height={preset['height']}", f"--fps={preset['fps']}",
            f"--video-bitrate={preset['video_bitrate']}", f"--max-rate={preset['max_rate']}",
            f"--buffer-size={preset['buffer_size']}", f"--x264-preset={preset['x264_preset']}",
            "--concurrency=1" if preview else "--concurrency=25%",
            "--media-cache-size-in-bytes=251658240",
            "--offthreadvideo-cache-size-in-bytes=268435456",
            "--offthreadvideo-video-threads=1",
        ]
        output.parent.mkdir(parents=True, exist_ok=True)
        log_path = project_root / "metadata" / "logs" / f"remotion-{'preview' if preview else 'final'}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(command, cwd=self.repo_root / "remotion", stdout=log,
                                       stderr=subprocess.STDOUT, check=False)
        if completed.returncode != 0:
            detail = " | ".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-4:])
            raise RuntimeError(f"Remotion render failed: {detail or f'exit code {completed.returncode}'}. See {log_path}")
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
        completed = subprocess.run([
            str(self._ffmpeg()), "-y", "-loglevel", "error", "-i", str(source),
            "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(output),
        ], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"FFmpeg finalization failed: {(completed.stderr or '').strip()[-500:]}")
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

    def _preflight(self, *, final: bool, require_audio: bool = True) -> dict:
        """Validate creator approval gates for a new local studio project.

        Legacy projects retain their existing render path.  New projects are
        intentionally stricter: no unattended render may skip source review,
        script approval, voice approval, or generated narration audio.
        """

        if not self._is_desktop_project():
            return {}
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        remotion = json.loads((self.project_root / "remotion.json").read_text(encoding="utf-8"))
        decisions = (manifest.get("render") or {}).get("scene_decisions") or {}
        included = [scene for scene in remotion.get("scenes", []) if decisions.get(scene.get("id")) != "cut"]
        missing: list[str] = []
        if not included:
            missing.append("at least one kept scene")
        if not manifest.get("script", {}).get("approved"):
            missing.append("script mapping approval")
        if not manifest.get("voice", {}).get("approved"):
            missing.append("voice approval")
        for scene in included:
            scene_id = str(scene.get("id", "unknown"))
            metadata_path = self.project_root / "scenes" / scene_id / "metadata.json"
            if not metadata_path.is_file() or not json.loads(metadata_path.read_text(encoding="utf-8")).get("approved_version"):
                missing.append(f"approved video for {scene_id}")
            if not str(scene.get("narration", "")).strip():
                missing.append(f"script for {scene_id}")
            audio = self.project_root / str(scene.get("narrationAudio", ""))
            if require_audio and not audio.is_file():
                missing.append(f"narration audio for {scene_id}")
        render = manifest.get("render", {})
        if final and not render.get("preview_approved"):
            missing.append("preview approval before final render")
        if final and render.get("review_dirty"):
            missing.append("an updated preview after scene edits")
        if missing:
            raise RuntimeError("Render is blocked until: " + "; ".join(missing))
        return manifest

    def _prepare_render_config(self, manifest: dict, quality: str) -> None:
        if not self._is_desktop_project():
            return
        preset = RENDER_PRESETS[quality]
        source = json.loads((self.project_root / "remotion.json").read_text(encoding="utf-8"))
        source.update({"width": preset["width"], "height": preset["height"], "fps": preset["fps"]})
        decisions = (manifest.get("render") or {}).get("scene_decisions") or {}
        source["scenes"] = [scene for scene in source.get("scenes", []) if decisions.get(scene.get("id")) != "cut"]
        render_root = self.project_root / "render"
        render_root.mkdir(parents=True, exist_ok=True)
        (render_root / "render-remotion.json").write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (render_root / "render-props.json").write_text(
            json.dumps({"projectSlug": self.project_name, "configFile": "render/render-remotion.json"}) + "\n", encoding="utf-8",
        )

    def _validate_output(self, path: Path, quality: str, stage: str) -> dict:
        """Fail a render whose real ffprobe metadata does not match its preset."""
        preset = RENDER_PRESETS[quality]
        actual = probe_video(path, self.repo_root)
        errors: list[str] = []
        if (actual["width"], actual["height"]) != (preset["width"], preset["height"]):
            errors.append(
                f"resolution {actual['width']}x{actual['height']} != {preset['width']}x{preset['height']}"
            )
        if abs(float(actual["fps"]) - preset["fps"]) > 0.01:
            errors.append(f"fps {actual['fps']} != {preset['fps']}")
        if actual["codec"] != "h264":
            errors.append(f"video codec {actual['codec']} != h264")
        if actual["pixel_format"] != "yuv420p":
            errors.append(f"pixel format {actual['pixel_format']} != yuv420p")
        if not actual["has_audio"] or actual["audio_codec"] != "aac":
            errors.append(f"audio codec {actual['audio_codec'] or 'missing'} != aac")
        bitrate = int(actual.get("video_bitrate") or 0)
        warnings: list[str] = []
        if bitrate and not preset["min_video_bitrate"] <= bitrate <= preset["max_video_bitrate"]:
            warnings.append(
                f"video bitrate {bitrate} is outside recommended "
                f"{preset['min_video_bitrate']}–{preset['max_video_bitrate']} bps"
            )
        report = {
            "quality": quality, "stage": stage, "path": str(path),
            "expected": {key: preset[key] for key in ("width", "height", "fps", "video_bitrate")},
            "actual": actual, "passed": not errors, "errors": errors, "warnings": warnings,
        }
        report_path = self.project_root / "metadata" / "logs" / f"render-validation-{stage}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if errors:
            raise RuntimeError(f"{quality.capitalize()} output validation failed: " + "; ".join(errors))
        return report

    def approve_preview(self) -> dict:
        """Record the creator's review decision before a full final render."""

        if not self._is_desktop_project():
            return self.state.set("APPROVED", "legacy preview approved")
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        preview = self.project_root / "render" / "preview" / "preview.mp4"
        if not (manifest.get("render") or {}).get("preview_ready") or not preview.is_file():
            raise RuntimeError("Render and review a preview before approving final render.")
        if (manifest.get("render") or {}).get("review_dirty"):
            raise RuntimeError("Render an updated preview after scene edits before approval.")
        manifest["render"] = {**dict(manifest.get("render") or {}), "preview_ready": True, "preview_approved": True}
        manifest["status"] = "READY_TO_RENDER"
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.state.set("READY_TO_RENDER", "preview approved by creator")
        return manifest

    def render_preview(self) -> Path:
        manifest = self._preflight(final=False)
        self._prepare_render_config(manifest, "preview")
        output = self.project_root / ("render/preview/preview.mp4" if self._is_desktop_project() else "output/preview.mp4")
        self.state.set("RENDERING", "preview")
        try:
            self.renderer.render(self.project_name, output, preview=True)
            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError("Preview renderer did not create a video file.")
            self._validate_output(output, "preview", "preview")
        except Exception:
            self.state.set("NEEDS_CHANGES", "preview render failed")
            raise
        if self._is_desktop_project():
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            manifest["render"] = {**dict(manifest.get("render") or {}), "preview_ready": True, "preview_approved": False,
                                  "review_dirty": False, "final_ready": False}
            manifest["status"] = "POST_RENDER_REVIEW"
            self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.state.set("POST_RENDER_REVIEW", "preview ready for creator review")
        else:
            self.state.set("REVIEW", "preview ready")
        return output

    def render_final(self) -> Path:
        manifest = self._preflight(final=True)
        self._prepare_render_config(manifest, "final")
        if self._is_desktop_project():
            intermediate = self.project_root / "render" / "final" / "final_remotion.mp4"
            output = self.project_root / "render" / "final" / "final.mp4"
        else:
            intermediate = self.project_root / "output" / "final_remotion.mp4"
            output = self.project_root / "output" / "final.mp4"
        self.state.set("RENDERING", "final")
        try:
            self.renderer.render(self.project_name, intermediate, preview=False)
            self._validate_output(intermediate, "final", "final-remotion")
            self.finalizer.finalize(intermediate, output)
            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError("Finalizer did not create a video file.")
            self._validate_output(output, "final", "final")
        except Exception:
            self.state.set("NEEDS_CHANGES", "final render failed")
            raise
        if self._is_desktop_project():
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            manifest["render"] = {**dict(manifest.get("render") or {}), "final_ready": True}
            manifest["status"] = "POST_RENDER_REVIEW"
            self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.state.set("POST_RENDER_REVIEW", "final ready for creator review")
        else:
            self.state.set("REVIEW", "final ready")
        return output
