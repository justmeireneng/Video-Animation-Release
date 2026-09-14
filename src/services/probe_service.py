from pathlib import Path
from typing import Any

from src.video.scene_source_manager import probe_video


class ProbeService:
    def __init__(self, repo_root: Path | str):
        self.repo_root = Path(repo_root).resolve()

    def probe(self, path: Path | str) -> dict[str, Any]:
        return probe_video(Path(path).resolve(), self.repo_root)
