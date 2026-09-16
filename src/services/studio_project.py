"""Local-first project creation and persistence for AI Video Studio.

The existing renderer reads ``remotion.json``.  This module adds a stable,
user-facing ``project.json`` and the on-disk layout used by the desktop app
without changing legacy projects.  It deliberately performs no network or
model setup.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_SCHEMA_VERSION = 1
DEFAULT_FPS = 30
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
DEFAULT_VOICE = {
    "provider": "omnivoice",
    "mode": "voice_design",
    "language": "vi",
    "locale": "default",
    "design": {"gender": "male", "age": "young adult", "pitch": "moderate"},
    "speed": 1.10,
    "approved": False,
}
DEFAULT_SOURCE_AUDIO = {
    "enabled": True,
    "mode": "background",
    "volume": 0.30,
    "duck_under_narration": True,
    "fade_in": 0.15,
    "fade_out": 0.20,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def slugify_project_name(name: str) -> str:
    """Return a safe, readable project directory name without trusting input."""

    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return (slug or "untitled-project")[:64]


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def manifest(self) -> Path:
        return self.root / "project.json"

    @property
    def remotion(self) -> Path:
        return self.root / "remotion.json"

    @property
    def script_text(self) -> Path:
        return self.root / "script" / "script.txt"

    @property
    def script_scenes(self) -> Path:
        return self.root / "script" / "scenes.json"


class LocalProjectManager:
    """Create and maintain projects below a caller-owned ``projects`` root.

    ``workspace_root`` is normally the repository root during development.
    A packaged desktop app can pass its user-data workspace instead, keeping
    projects outside Program Files.
    """

    def __init__(self, workspace_root: Path | str):
        self.workspace_root = Path(workspace_root).resolve()
        self.projects_root = self.workspace_root / "projects"

    def paths(self, project_id: str) -> ProjectPaths:
        candidate = (self.projects_root / project_id).resolve()
        if not candidate.is_relative_to(self.projects_root.resolve()):
            raise ValueError("Project id resolves outside the projects directory.")
        return ProjectPaths(candidate)

    def create(self, name: str, *, project_id: str | None = None) -> dict[str, Any]:
        display_name = str(name).strip()
        if not display_name:
            raise ValueError("A project name is required.")
        identifier = slugify_project_name(project_id or display_name)
        paths = self.paths(identifier)
        suffix = 2
        while paths.root.exists():
            paths = self.paths(f"{identifier}-{suffix}")
            suffix += 1
        self._create_layout(paths)
        manifest = {
            "schema_version": PROJECT_SCHEMA_VERSION,
            "id": paths.root.name,
            "name": display_name,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "status": "DRAFT",
            "source": {"imported": False, "last_import": None},
            "script": {"approved": False, "path": "script/script.txt", "scene_map": "script/scenes.json"},
            "voice": dict(DEFAULT_VOICE),
            "subtitles": {
                "font": "Be Vietnam Pro",
                "weight": "SemiBold",
                "size": 55,
                "position": "bottom",
                "vertical_offset": 102,
                "highlight_current_phrase": True,
                "safe_zone": True,
            },
            "audio": {"bgm": None, "sfx": [], "narration_volume": 1.0, "bgm_volume": 0.12},
            "render": {"preview_ready": False, "final_ready": False, "approval": False},
        }
        _write_json(paths.manifest, manifest)
        _write_json(paths.remotion, self._empty_remotion(display_name))
        _write_json(paths.root / "remotion-props.json", {"projectSlug": paths.root.name, "configFile": "remotion.json"})
        paths.script_text.write_text("", encoding="utf-8")
        _write_json(paths.script_scenes, {"scenes": []})
        _write_json(paths.root / "project-state.json", {"status": "DRAFT", "history": []})
        return manifest

    def list(self) -> list[dict[str, Any]]:
        if not self.projects_root.is_dir():
            return []
        projects: list[dict[str, Any]] = []
        for manifest in sorted(self.projects_root.glob("*/project.json"), key=lambda path: path.stat().st_mtime, reverse=True):
            try:
                projects.append(_read_json(manifest))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return projects

    def load(self, project_id: str) -> dict[str, Any]:
        paths = self.paths(project_id)
        if not paths.manifest.is_file():
            raise FileNotFoundError(f"Project manifest not found: {paths.manifest}")
        return _read_json(paths.manifest)

    def save(self, project_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
        paths = self.paths(project_id)
        if not paths.root.is_dir():
            raise FileNotFoundError(f"Project not found: {paths.root}")
        saved = dict(manifest)
        saved["id"] = paths.root.name
        saved["schema_version"] = PROJECT_SCHEMA_VERSION
        saved["updated_at"] = _utc_now()
        _write_json(paths.manifest, saved)
        return saved

    def ensure_scene_slots(self, project_id: str, scene_numbers: Iterable[int]) -> dict[str, Any]:
        """Create missing slots from imported filenames, including numeric gaps.

        Scene 10 in a ZIP intentionally creates slots 1 through 10 so the UI
        can show missing scenes instead of silently reindexing the user's
        source.  Existing narration and video metadata are never overwritten.
        """

        paths = self.paths(project_id)
        project = _read_json(paths.remotion)
        numbers = sorted({int(number) for number in scene_numbers if int(number) > 0})
        if not numbers:
            return project
        existing = {int(scene.get("index", 0)): scene for scene in project.get("scenes", [])}
        for number in range(1, numbers[-1] + 1):
            if number not in existing:
                project.setdefault("scenes", []).append(self._new_scene(number))
        project["scenes"] = sorted(project["scenes"], key=lambda scene: int(scene["index"]))
        _write_json(paths.remotion, project)
        manifest = self.load(project_id)
        manifest["source"] = {**dict(manifest.get("source") or {}), "scene_count": len(project["scenes"])}
        self.save(project_id, manifest)
        return project

    @staticmethod
    def _create_layout(paths: ProjectPaths) -> None:
        for relative in (
            "source/imported", "source/scenes", "scenes", "script", "voice/previews", "voice/narration",
            "voice/cache", "subtitles/scenes", "subtitles/final", "audio/bgm", "audio/sfx", "audio/temp",
            "render/preview", "render/final", "metadata/probes", "metadata/logs",
        ):
            (paths.root / relative).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _empty_remotion(name: str) -> dict[str, Any]:
        return {
            "name": name,
            "fps": DEFAULT_FPS,
            "width": DEFAULT_WIDTH,
            "height": DEFAULT_HEIGHT,
            "style": "cartoon_explainer",
            "mascot": {"idle": ""},
            "sourceVideoSettings": {"auto_approve_latest": False, "source_audio_default": dict(DEFAULT_SOURCE_AUDIO)},
            "audio": {},
            "scenes": [],
        }

    @staticmethod
    def _new_scene(number: int) -> dict[str, Any]:
        scene_id = f"scene_{number:02d}"
        return {
            "id": scene_id,
            "index": number,
            "approved": False,
            "durationInFrames": 5 * DEFAULT_FPS,
            "narration": "",
            "narrationAudio": f"voice/narration/{scene_id}.wav",
            "subtitle": [],
            "layout": "full_bleed",
            "mascotPose": "idle",
            "animation": {"type": "slow_push_in"},
            "focalPoint": {"x": 0.5, "y": 0.5},
            "transition": "none",
            "videoSources": [],
            "currentVideoVersion": None,
        }
