from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCENE_PATTERN = re.compile(r"scene[_ -]?(\d+)", re.IGNORECASE)
MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


@dataclass(frozen=True)
class SceneFile:
    path: Path
    number: int


class SceneMapper:
    @staticmethod
    def detect(path: Path) -> SceneFile | None:
        match = SCENE_PATTERN.search(path.stem)
        return SceneFile(path=path, number=int(match.group(1))) if match else None

    @classmethod
    def scan(cls, root: Path) -> tuple[list[SceneFile], list[Path]]:
        detected: list[SceneFile] = []
        unmatched: list[Path] = []
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in MEDIA_EXTENSIONS:
                continue
            item = cls.detect(path)
            (detected if item else unmatched).append(item if item else path)
        return sorted(detected, key=lambda item: (item.number, item.path.name.lower())), sorted(unmatched)

    @staticmethod
    def scene_map(project: dict[str, Any]) -> dict[int, str]:
        scenes = sorted(project.get("scenes", []), key=lambda scene: int(scene.get("index", 0)))
        by_index: dict[int, str] = {}
        for position, scene in enumerate(scenes, 1):
            raw_index = scene.get("index")
            try:
                number = int(raw_index) if raw_index is not None else position
            except (TypeError, ValueError):
                number = position
            if number <= 0 or number in by_index:
                number = position
            by_index[number] = str(scene["id"])
        return by_index
