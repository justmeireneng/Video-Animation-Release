#!/usr/bin/env python3
"""Versioned scene-video storage used by CLI, import, review, and render services."""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from src.services.audio_policy import AudioPolicyService
from src.services.source_version_manager import SourceVersionManager


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def find_ffprobe(repo_root: Path) -> Path:
    system = shutil.which("ffprobe")
    if system:
        return Path(system)
    pattern = "remotion/node_modules/.pnpm/@remotion+compositor-*/node_modules/@remotion/compositor-*/ffprobe.exe"
    candidates = sorted(repo_root.glob(pattern))
    if not candidates:
        raise FileNotFoundError("ffprobe not found in PATH or the installed Remotion compositor.")
    return candidates[-1]


def probe_video(path: Path, repo_root: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    result = subprocess.run(
        [str(find_ffprobe(repo_root)), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    raw = json.loads(result.stdout)
    video_stream = next((item for item in raw.get("streams", []) if item.get("codec_type") == "video"), None)
    if not video_stream:
        raise ValueError(f"Imported file has no video stream: {path}")
    audio_stream = next((item for item in raw.get("streams", []) if item.get("codec_type") == "audio"), None)
    rate = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "0/1"
    try:
        fps = float(Fraction(rate))
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    duration = float(video_stream.get("duration") or raw.get("format", {}).get("duration") or 0)
    if duration <= 0 or width <= 0 or height <= 0:
        raise ValueError(f"Unreadable video metadata: {path}")
    return {
        "duration": round(duration, 3), "width": width, "height": height, "fps": round(fps, 3),
        "codec": video_stream.get("codec_name", "unknown"), "pixel_format": video_stream.get("pix_fmt", "unknown"),
        "has_audio": audio_stream is not None, "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        "aspect_ratio": f"{width}:{height}", "portrait": height >= width, "readable": True,
    }


def _timing_policy(source_duration: float, target_duration: float) -> dict[str, Any]:
    if source_duration <= 0 or target_duration <= 0:
        return {"playback_rate": 1.0, "hold_last_frame": False, "loop": False}
    if source_duration > target_duration * 1.1:
        return {"playback_rate": 1.0, "hold_last_frame": False, "loop": False, "recommended_trim_end": round(target_duration, 3)}
    playback_rate = source_duration / target_duration
    if 0.9 <= playback_rate <= 1.1:
        return {"playback_rate": round(playback_rate, 4), "hold_last_frame": False, "loop": False}
    return {"playback_rate": 1.0, "hold_last_frame": source_duration < target_duration, "loop": False}


class SceneVideoStore:
    def __init__(self, repo_root: Path | str, project_name: str,
                 prober: Callable[[Path, Path], dict[str, Any]] = probe_video) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.project_name = project_name
        self.project_root = self.repo_root / "projects" / project_name
        self.remotion_path = self.project_root / "remotion.json"
        self.prober = prober
        if not self.project_root.is_dir():
            raise FileNotFoundError(f"Project not found: {self.project_root}")
        if not self.remotion_path.is_file():
            raise FileNotFoundError(f"Remotion project JSON not found: {self.remotion_path}")

    def _project(self) -> dict[str, Any]:
        return _read_json(self.remotion_path)

    def _scene(self, scene_id: str) -> dict[str, Any]:
        scene = next((item for item in self._project().get("scenes", []) if item.get("id") == scene_id), None)
        if scene is None:
            raise ValueError(f"Unknown scene: {scene_id}")
        return scene

    def _fps(self) -> float:
        return float(self._project().get("fps", 30))

    def _settings(self) -> dict[str, Any]:
        return self._project().get("sourceVideoSettings", {})

    def metadata_path(self, scene_id: str) -> Path:
        return self.project_root / "scenes" / scene_id / "metadata.json"

    def load_metadata(self, scene_id: str) -> dict[str, Any]:
        path = self.metadata_path(scene_id)
        if path.exists():
            return _read_json(path)
        scene = self._scene(scene_id)
        duration = scene["durationInFrames"] / self._fps()
        metadata = {
            "scene_id": scene_id, "narration": scene.get("narration", ""), "source_video": None,
            "source_provider": None, "source_filename": None, "status": "missing", "duration": duration,
            "trim": {"start": 0.0, "end": None}, "crop": {"mode": "cover", "x": 0.5, "y": 0.5},
            "source_audio": AudioPolicyService.defaults(False), "version": 0, "active_version": None,
            "approved_version": None, "versions": [],
        }
        _write_json(path, metadata)
        return metadata

    def import_video(self, scene_id: str, source_file: Path | str, provider: str = "google_flow_manual",
                     source_filename: str | None = None) -> dict[str, Any]:
        source = Path(source_file).resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        metadata = self.load_metadata(scene_id)
        version = SourceVersionManager.next_version(metadata)
        relative = SourceVersionManager.relative_path(scene_id, version, prefix="flow")
        destination = self.project_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(f"Version destination already exists: {destination}")
        try:
            media = self.prober(source, self.repo_root)
            status, error = "pending_review", None
        except Exception as exc:
            media = {"duration": 0.0, "width": 0, "height": 0, "fps": 0.0, "codec": "unknown", "has_audio": False, "readable": False}
            status, error = "invalid", str(exc)
        shutil.copy2(source, destination)
        target_duration = float(self._scene(scene_id)["durationInFrames"]) / self._fps()
        timing = _timing_policy(float(media["duration"]), target_duration)
        trim_end = timing.pop("recommended_trim_end", None)
        source_audio = AudioPolicyService.defaults(bool(media.get("has_audio")), self._settings().get("source_audio_default"))
        record = {
            "scene_id": scene_id, "source_provider": provider, "source_filename": source_filename or source.name,
            "source_video": relative.as_posix(), "version": version, "probe": media, "status": status,
            "trim": {"start": 0.0, "end": trim_end}, "crop": {"mode": "cover", "x": 0.5, "y": 0.5},
            "source_audio": source_audio, "timing": timing, "created_at": _utc_now(),
        }
        if error:
            record["error"] = error
        metadata["versions"].append(record)
        self._select(metadata, record)
        if status != "invalid" and self._settings().get("auto_approve_latest") is True:
            record["status"] = "approved"
            metadata["approved_version"] = version
            metadata["status"] = "approved"
        _write_json(self.metadata_path(scene_id), metadata)
        self._sync_remotion(scene_id, metadata)
        return record

    def approve(self, scene_id: str, version: int) -> dict[str, Any]:
        metadata = self.load_metadata(scene_id)
        record = self._version(metadata, version)
        if record["status"] == "invalid":
            raise ValueError("Invalid source video cannot be approved.")
        for item in metadata["versions"]:
            if item["status"] == "approved":
                item["status"] = "available"
        record["status"] = "approved"
        record["reviewed_at"] = _utc_now()
        metadata["approved_version"] = version
        self._select(metadata, record)
        _write_json(self.metadata_path(scene_id), metadata)
        self._sync_remotion(scene_id, metadata)
        return record

    def reject(self, scene_id: str, version: int) -> dict[str, Any]:
        metadata = self.load_metadata(scene_id)
        record = self._version(metadata, version)
        record["status"] = "rejected"
        record["reviewed_at"] = _utc_now()
        if metadata.get("approved_version") == version:
            metadata["approved_version"] = None
        self._select(metadata, record)
        _write_json(self.metadata_path(scene_id), metadata)
        self._sync_remotion(scene_id, metadata)
        return record

    def set_trim(self, scene_id: str, version: int, start: float, end: float) -> dict[str, Any]:
        metadata = self.load_metadata(scene_id)
        record = self._version(metadata, version)
        duration = float(record["probe"]["duration"])
        if start < 0 or end <= start or end > duration + 0.05:
            raise ValueError(f"Invalid trim {start}-{end}; clip duration is {duration}s.")
        record["trim"] = {"start": round(start, 3), "end": round(end, 3)}
        record["timing"] = _timing_policy(end - start, float(self._scene(scene_id)["durationInFrames"]) / self._fps())
        self._select(metadata, record)
        _write_json(self.metadata_path(scene_id), metadata)
        self._sync_remotion(scene_id, metadata)
        return record

    def set_crop(self, scene_id: str, version: int, x: float, y: float, mode: str = "cover") -> dict[str, Any]:
        if mode not in {"cover", "contain"} or not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ValueError("Crop requires mode cover/contain and x/y in the 0..1 range.")
        metadata = self.load_metadata(scene_id)
        record = self._version(metadata, version)
        record["crop"] = {"mode": mode, "x": round(x, 4), "y": round(y, 4)}
        self._select(metadata, record)
        _write_json(self.metadata_path(scene_id), metadata)
        self._sync_remotion(scene_id, metadata)
        return record

    def set_source_audio(self, scene_id: str, version: int, mode: str, volume: float | None = None,
                         duck: bool | None = None, fade_in: float | None = None,
                         fade_out: float | None = None) -> dict[str, Any]:
        metadata = self.load_metadata(scene_id)
        record = self._version(metadata, version)
        record["source_audio"] = AudioPolicyService.update(
            record["source_audio"], mode=mode, volume=volume, duck=duck, fade_in=fade_in, fade_out=fade_out,
        )
        self._select(metadata, record)
        _write_json(self.metadata_path(scene_id), metadata)
        self._sync_remotion(scene_id, metadata)
        return record

    def set_transition(self, scene_id: str, transition: str) -> dict[str, Any]:
        if transition not in {"crossfade", "soft_slide", "wipe_reveal", "paper", "none"}:
            raise ValueError("Unsupported transition.")
        project = self._project()
        scene = next((item for item in project["scenes"] if item["id"] == scene_id), None)
        if scene is None:
            raise ValueError(f"Unknown scene: {scene_id}")
        scene["transition"] = transition
        _write_json(self.remotion_path, project)
        return scene

    def set_subtitle_offset(self, scene_id: str, offset_y: int) -> dict[str, Any]:
        project = self._project()
        scene = next((item for item in project["scenes"] if item["id"] == scene_id), None)
        if scene is None:
            raise ValueError(f"Unknown scene: {scene_id}")
        scene["subtitleOffsetY"] = max(-500, min(500, int(offset_y)))
        _write_json(self.remotion_path, project)
        return scene

    @staticmethod
    def _version(metadata: dict[str, Any], version: int) -> dict[str, Any]:
        record = next((item for item in metadata["versions"] if int(item["version"]) == version), None)
        if record is None:
            raise ValueError(f"Unknown video version: {version}")
        return record

    @staticmethod
    def _select(metadata: dict[str, Any], record: dict[str, Any]) -> None:
        metadata.update({
            "source_video": record["source_video"], "source_provider": record["source_provider"],
            "source_filename": record["source_filename"], "status": record["status"],
            "duration": record["probe"]["duration"], "trim": record["trim"], "crop": record["crop"],
            "source_audio": record["source_audio"], "version": record["version"], "active_version": record["version"],
        })

    def _sync_remotion(self, scene_id: str, metadata: dict[str, Any]) -> None:
        project = self._project()
        scene = next(item for item in project["scenes"] if item["id"] == scene_id)
        self._apply_metadata_to_scene(scene, metadata)
        project.setdefault("sourceVideoSettings", {
            "auto_approve_latest": False,
            "source_audio_default": {"mode": "background", "volume": 0.30, "duck_under_narration": True},
        })
        _write_json(self.remotion_path, project)

    @staticmethod
    def _apply_metadata_to_scene(scene: dict[str, Any], metadata: dict[str, Any]) -> None:
        scene["videoSources"] = [
            {
                "src": item["source_video"], "provider": item["source_provider"],
                "sourceFilename": item["source_filename"], "version": item["version"], "review": item["status"],
                "duration": item["probe"]["duration"],
                "trim": {"start": item["trim"]["start"], "end": item["trim"]["end"] or item["probe"]["duration"]},
                "crop": item["crop"], "playbackRate": item.get("timing", {}).get("playback_rate", 1.0),
                "holdLastFrame": item.get("timing", {}).get("hold_last_frame", False),
                "loop": item.get("timing", {}).get("loop", False), "sourceAudio": item["source_audio"],
            }
            for item in metadata["versions"] if item["status"] != "invalid"
        ]
        scene["currentVideoVersion"] = metadata.get("active_version")

    def sync_all_to_remotion(self) -> None:
        """Restore source-video projections without touching narration or visual edits."""

        project = self._project()
        scenes = {str(item.get("id")): item for item in project.get("scenes", [])}
        for scene_id, scene in scenes.items():
            metadata_path = self.metadata_path(scene_id)
            if metadata_path.is_file():
                self._apply_metadata_to_scene(scene, _read_json(metadata_path))
        project.setdefault("sourceVideoSettings", {
            "auto_approve_latest": False,
            "source_audio_default": {"mode": "background", "volume": 0.30, "duck_under_narration": True},
        })
        _write_json(self.remotion_path, project)
