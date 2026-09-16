"""Script import, per-scene mapping, and readiness validation.

The text supplied by the creator remains the source of truth.  This module
parses labels and stores them; it never invents or rewrites narration.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.services.studio_project import LocalProjectManager, ProjectPaths


SCENE_HEADER = re.compile(r"(?im)^\s*scene\s*[_ -]?(\d+)\s*$")
NARRATION_LABEL = re.compile(r"(?im)^\s*narration\s*:\s*(.*)$")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@dataclass(frozen=True)
class ParsedScript:
    scene_number: int
    narration: str


class ScriptParser:
    @staticmethod
    def parse(text: str) -> tuple[list[ParsedScript], list[str]]:
        matches = list(SCENE_HEADER.finditer(text))
        if not matches:
            return [], ["No SCENE <number> blocks were found."]
        blocks: list[ParsedScript] = []
        errors: list[str] = []
        seen: set[int] = set()
        for index, header in enumerate(matches):
            number = int(header.group(1))
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[header.end():end]
            label = NARRATION_LABEL.search(body)
            if label is None:
                errors.append(f"Scene {number}: missing Narration: label.")
                continue
            narration = (label.group(1) + body[label.end():]).strip()
            if narration.startswith(('"', '“')) and narration.endswith(('"', '”')) and len(narration) >= 2:
                narration = narration[1:-1]
            if not narration.strip():
                errors.append(f"Scene {number}: narration is empty.")
                continue
            if number in seen:
                errors.append(f"Scene {number}: duplicate script block.")
                continue
            seen.add(number)
            blocks.append(ParsedScript(number, narration))
        return sorted(blocks, key=lambda item: item.scene_number), errors


class ScriptService:
    def __init__(self, workspace_root: Path | str, project_id: str):
        self.manager = LocalProjectManager(workspace_root)
        self.project_id = project_id
        self.paths: ProjectPaths = self.manager.paths(project_id)
        if not self.paths.root.is_dir():
            raise FileNotFoundError(f"Project not found: {self.paths.root}")

    def save_bulk(self, text: str) -> dict[str, Any]:
        parsed, errors = ScriptParser.parse(text)
        self.paths.script_text.write_text(text, encoding="utf-8")
        project = json.loads(self.paths.remotion.read_text(encoding="utf-8"))
        by_index = {int(scene["index"]): scene for scene in project.get("scenes", [])}
        mapped: list[int] = []
        unknown: list[int] = []
        for item in parsed:
            scene = by_index.get(item.scene_number)
            if scene is None:
                unknown.append(item.scene_number)
                continue
            scene["narration"] = item.narration
            mapped.append(item.scene_number)
        project["scenes"] = sorted(project.get("scenes", []), key=lambda scene: int(scene["index"]))
        _write_json(self.paths.remotion, project)
        validation = self.validation(project)
        report = {
            "mapped_scene_numbers": mapped,
            "unknown_scene_numbers": unknown,
            "errors": errors,
            "validation": validation,
        }
        _write_json(self.paths.script_scenes, report)
        manifest = self.manager.load(self.project_id)
        manifest["script"] = {**dict(manifest.get("script") or {}), "approved": False}
        manifest["status"] = "SCRIPT_MAPPING"
        self.manager.save(self.project_id, manifest)
        return report

    def import_text_file(self, source: Path | str) -> dict[str, Any]:
        path = Path(source).resolve()
        if not path.is_file() or path.suffix.lower() != ".txt":
            raise ValueError("Script import requires a readable .txt file.")
        return self.save_bulk(path.read_text(encoding="utf-8-sig"))

    def update_scene(self, scene_number: int, narration: str) -> dict[str, Any]:
        if scene_number <= 0 or not narration.strip():
            raise ValueError("Scene number must be positive and narration cannot be empty.")
        project = json.loads(self.paths.remotion.read_text(encoding="utf-8"))
        scene = next((item for item in project.get("scenes", []) if int(item.get("index", 0)) == scene_number), None)
        if scene is None:
            raise ValueError(f"Unknown scene {scene_number}.")
        scene["narration"] = narration
        _write_json(self.paths.remotion, project)
        blocks = [
            f"SCENE {int(item['index'])}\nNarration:\n\"{item.get('narration', '')}\""
            for item in sorted(project.get("scenes", []), key=lambda current: int(current["index"]))
            if str(item.get("narration", "")).strip()
        ]
        return self.save_bulk("\n\n".join(blocks))

    def approve_mapping(self) -> dict[str, Any]:
        validation = self.validation()
        missing = [item["scene_number"] for item in validation if item["script"] != "SCRIPT_OK"]
        if missing:
            raise ValueError(f"Cannot approve script mapping; narration is missing for scene(s): {missing}.")
        manifest = self.manager.load(self.project_id)
        manifest["script"] = {**dict(manifest.get("script") or {}), "approved": True}
        manifest["status"] = "VOICE_SETUP"
        return self.manager.save(self.project_id, manifest)

    def validation(self, project: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        project = project or json.loads(self.paths.remotion.read_text(encoding="utf-8"))
        result: list[dict[str, Any]] = []
        for scene in sorted(project.get("scenes", []), key=lambda item: int(item["index"])):
            scene_id = str(scene["id"])
            metadata_path = self.paths.root / "scenes" / scene_id / "metadata.json"
            video_status = "VIDEO_MISSING"
            if metadata_path.is_file():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if metadata.get("approved_version"):
                    video_status = "VIDEO_OK"
                elif metadata.get("versions"):
                    video_status = "VIDEO_PENDING_REVIEW"
            script_status = "SCRIPT_OK" if str(scene.get("narration", "")).strip() else "SCRIPT_MISSING"
            result.append({
                "scene_id": scene_id,
                "scene_number": int(scene["index"]),
                "video": video_status,
                "script": script_status,
                "ready": video_status == "VIDEO_OK" and script_status == "SCRIPT_OK",
            })
        return result
