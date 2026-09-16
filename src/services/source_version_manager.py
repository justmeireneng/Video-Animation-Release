from pathlib import Path
from typing import Any


class SourceVersionManager:
    @staticmethod
    def next_version(metadata: dict[str, Any]) -> int:
        return max((int(item["version"]) for item in metadata.get("versions", [])), default=0) + 1

    @staticmethod
    def relative_path(scene_id: str, version: int, prefix: str = "flow", suffix: str = ".mp4") -> Path:
        extension = suffix.lower() if suffix.startswith(".") else f".{suffix.lower()}"
        if extension not in {".mp4", ".mov", ".mkv", ".webm", ".m4v"}:
            raise ValueError(f"Unsupported source-media extension: {extension}")
        return Path("scenes") / scene_id / "source" / f"{prefix}_v{version}{extension}"
