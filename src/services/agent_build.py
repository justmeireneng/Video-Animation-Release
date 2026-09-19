"""Agent-first, one-command video build orchestration.

The desktop UI remains an optional review surface.  This service is the
stable automation boundary for ZIP + script -> validated final MP4.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.import_service import ImportService
from src.services.narration_timeline import NarrationTimelineService
from src.services.project_state import ProjectStateService
from src.services.render_service import RenderService
from src.services.script_service import ScriptService
from src.services.studio_project import LocalProjectManager, slugify_project_name
from src.services.voice_service import DEFAULT_VOICE_MODE
from src.video.scene_source_manager import SceneVideoStore


class AgentBuildError(RuntimeError):
    """A build could not safely proceed to final rendering."""


class AgentBuildService:
    """Run the unattended local pipeline while preserving project state."""

    def __init__(self, repo_root: Path | str):
        self.repo_root = Path(repo_root).resolve()
        self.projects = LocalProjectManager(self.repo_root)

    def _ensure_project(self, project_name: str) -> tuple[str, dict[str, Any]]:
        project_id = slugify_project_name(project_name)
        paths = self.projects.paths(project_id)
        if paths.root.is_dir() and paths.manifest.is_file():
            return project_id, self.projects.load(project_id)
        manifest = self.projects.create(project_name, project_id=project_id)
        return str(manifest["id"]), manifest

    @staticmethod
    def _read_config(path: Path | str | None) -> dict[str, Any]:
        if path is None:
            return {}
        config_path = Path(path).resolve()
        if not config_path.is_file():
            raise FileNotFoundError(f"Project config not found: {config_path}")
        try:
            value = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid project_config.json: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("project_config.json must contain a JSON object.")
        return value

    def _apply_config(self, project_id: str, config: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        paths = self.projects.paths(project_id)
        manifest = self.projects.load(project_id)
        voice = config.get("voice")
        if isinstance(voice, dict):
            if voice.get("provider", "omnivoice") != "omnivoice":
                raise AgentBuildError("Only OmniVoice is active; project_config.voice.provider must be 'omnivoice'.")
            manifest["voice"] = {**dict(manifest.get("voice") or {}), **voice, "provider": "omnivoice", "approved": True}
        else:
            manifest["voice"] = {**dict(manifest.get("voice") or {}), "provider": "omnivoice", "approved": True}
        # Four diffusion steps are the safe unattended default for the current
        # CPU target. Higher quality remains opt-in via voice.num_step (4/8/16).
        requested_steps = int(manifest["voice"].get("num_step", 4))
        if requested_steps not in {4, 8, 16}:
            raise AgentBuildError("voice.num_step must be 4, 8, or 16.")
        manifest["voice"]["num_step"] = requested_steps
        self.projects.save(project_id, manifest)

        render = config.get("render")
        if isinstance(render, dict):
            expected = {"preview": (720, 1280, 30), "final": (1080, 1920, 30)}
            for quality, target in expected.items():
                value = render.get(quality)
                if isinstance(value, dict):
                    requested = (int(value.get("width", target[0])), int(value.get("height", target[1])), int(value.get("fps", target[2])))
                    if requested != target:
                        warnings.append(f"render.{quality} was normalized to {target[0]}x{target[1]}@{target[2]} to keep the production target.")

        scenes = config.get("scenes")
        if not isinstance(scenes, dict):
            return warnings
        store = SceneVideoStore(self.repo_root, project_id)
        remotion = json.loads(paths.remotion.read_text(encoding="utf-8"))
        by_index = {str(int(scene["index"])): scene for scene in remotion.get("scenes", [])}
        for number, settings in scenes.items():
            scene = by_index.get(str(number))
            if scene is None:
                warnings.append(f"Config references missing scene {number}.")
                continue
            scene_id = str(scene["id"])
            metadata = store.load_metadata(scene_id)
            if isinstance(settings, dict) and settings.get("source_version") is not None:
                requested_version = int(settings["source_version"])
                store.approve(scene_id, requested_version)
                metadata = store.load_metadata(scene_id)
            version = int(metadata.get("active_version") or 0)
            if not version:
                warnings.append(f"Config for scene {number} deferred until a source version exists.")
                continue
            if not isinstance(settings, dict):
                continue
            if "trim_start" in settings or "trim_end" in settings:
                current = next(item for item in metadata["versions"] if int(item["version"]) == version)
                start = float(settings.get("trim_start", current["trim"]["start"]))
                end = float(settings.get("trim_end", current["trim"]["end"] or current["probe"]["duration"]))
                store.set_trim(scene_id, version, start, end)
            if "speed" in settings or "playback_speed" in settings:
                store.set_playback_speed(scene_id, version, float(settings.get("speed", settings.get("playback_speed"))))
            crop = settings.get("crop")
            fit = settings.get("fit")
            if isinstance(crop, dict) or fit in {"cover", "contain"}:
                crop = crop if isinstance(crop, dict) else {}
                store.set_crop(scene_id, version, float(crop.get("focal_x", crop.get("x", 0.5))), float(crop.get("focal_y", crop.get("y", 0.5))), str(crop.get("mode", fit or "cover")))
            if "focal_x" in settings or "focal_y" in settings:
                current = store.load_metadata(scene_id)["crop"]
                store.set_crop(scene_id, version, float(settings.get("focal_x", current["x"])), float(settings.get("focal_y", current["y"])), current.get("mode", "cover"))
            if "hold_last_frame" in settings:
                store.set_hold_last_frame(scene_id, version, bool(settings["hold_last_frame"]))
            if "transition" in settings:
                transition = {"paper_reveal": "paper", "wipe": "wipe_reveal"}.get(str(settings["transition"]), str(settings["transition"]))
                store.set_transition(scene_id, transition)
            audio = settings.get("source_audio")
            if isinstance(audio, dict):
                store.set_source_audio(scene_id, version, str(audio.get("mode", "background")), audio.get("volume"), audio.get("duck_under_narration", audio.get("duck")), audio.get("fade_in"), audio.get("fade_out"))
        return warnings

    def _approve_first_valid_sources(self, project_id: str, import_report: dict[str, Any]) -> list[str]:
        store = SceneVideoStore(self.repo_root, project_id)
        warnings: list[str] = []
        for scene_id in import_report.get("mapped_scenes", []):
            metadata = store.load_metadata(scene_id)
            if metadata.get("approved_version"):
                continue
            valid = [item for item in metadata.get("versions", []) if item.get("status") != "invalid" and item.get("probe", {}).get("readable", True)]
            if valid:
                store.approve(scene_id, min(valid, key=lambda item: int(item["version"]))["version"])
            else:
                warnings.append(f"{scene_id} has no readable source version.")
        return warnings

    @staticmethod
    def _readiness(project_id: str, repo_root: Path) -> list[dict[str, Any]]:
        return ScriptService(repo_root, project_id).validation()

    def build(self, *, zip_path: Path | str, script_path: Path | str, project_name: str, config_path: Path | str | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        project_id, _ = self._ensure_project(project_name)
        project_root = self.projects.paths(project_id).root
        warnings: list[str] = []
        errors: list[str] = []
        report: dict[str, Any] = {
            "project_name": project_id, "input": {"zip": str(Path(zip_path).resolve()), "script": str(Path(script_path).resolve()), "config": str(Path(config_path).resolve()) if config_path else None},
            "stages": {}, "warnings": warnings, "errors": errors, "started_at": datetime.now(timezone.utc).isoformat(),
        }
        report_path = project_root / "build_report.json"
        try:
            config = self._read_config(config_path)
            report["stages"]["config"] = {"status": "ok", "provided": config_path is not None}
            imported = ImportService(self.repo_root, project_id).import_zip(zip_path)
            report["stages"]["import"] = {"status": "ok", "mapped_scenes": imported.get("mapped_scenes", []), "scene_map": imported.get("scene_map", []), "missing_scenes": imported.get("missing_scenes", [])}
            warnings.extend(imported.get("warnings", []))
            warnings.extend(self._approve_first_valid_sources(project_id, imported))
            script = ScriptService(self.repo_root, project_id).import_text_file(script_path)
            report["stages"]["mapping"] = {"status": "ok" if not script.get("errors") and not script.get("unknown_scene_numbers") else "error", **script}
            if script.get("errors") or script.get("unknown_scene_numbers"):
                raise AgentBuildError(f"Script mapping mismatch: errors={script.get('errors') or []}, unknown_scene_numbers={script.get('unknown_scene_numbers') or []}")
            readiness = self._readiness(project_id, self.repo_root)
            mismatch = [item for item in readiness if not item["ready"]]
            if mismatch:
                raise AgentBuildError("Video/script mismatch: " + "; ".join(f"scene {item['scene_number']} {item['video']}/{item['script']}" for item in mismatch))
            warnings.extend(self._apply_config(project_id, config))
            ScriptService(self.repo_root, project_id).approve_mapping()
            report["stages"]["validation"] = {"status": "ok", "scenes": readiness}
            narration = NarrationTimelineService(self.repo_root, project_id).prepare(synthesize=True)
            report["stages"]["voice_subtitles"] = {"status": "ok", "provider": narration["voice_provider"], "scenes": narration["scenes"], "duration": narration["total_narration_duration"]}
            render = RenderService(self.repo_root, project_id)
            preview = render.render_preview()
            report["stages"]["preview"] = {"status": "ok", "path": str(preview)}
            render.approve_preview()
            final = render.render_final()
            report["stages"]["final"] = {"status": "ok", "path": str(final)}
            report["status"] = "success"
        except Exception as exc:
            errors.append(str(exc))
            report["status"] = "failed"
            report["stages"].setdefault("failure", {"status": "error"})
        report["render_time_seconds"] = round(time.perf_counter() - started, 3)
        manifest = self.projects.load(project_id)
        report["voice"] = {"provider": manifest.get("voice", {}).get("provider", "omnivoice"), "language": manifest.get("voice", {}).get("language", "vi"), "speed": manifest.get("voice", {}).get("speed", 1.10)}
        report["outputs"] = {"preview": str(project_root / "render/preview/preview.mp4"), "final": str(project_root / "render/final/final.mp4"), "report": str(report_path)}
        validation_dir = project_root / "metadata" / "logs"
        validations: dict[str, Any] = {}
        for label, filename in (("preview", "render-validation-preview.json"), ("final", "render-validation-final.json")):
            path = validation_dir / filename
            if path.is_file():
                try:
                    validations[label] = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    warnings.append(f"Could not read {filename}.")
        report["validation"] = validations
        report["render"] = {
            "preview": {"width": 720, "height": 1280, "fps": 30},
            "final": {"width": 1080, "height": 1920, "fps": 30},
        }
        report["source_audio"] = manifest.get("audio", {})
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if errors:
            raise AgentBuildError(f"Build failed. See {report_path}: {errors[-1]}")
        return report
