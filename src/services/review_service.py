from pathlib import Path
from typing import Any

from src.video.scene_source_manager import SceneVideoStore


class ReviewService:
    def __init__(self, repo_root: Path | str, project_name: str):
        self.store = SceneVideoStore(repo_root, project_name)

    def approve(self, scene_id: str, version: int) -> dict[str, Any]:
        return self.store.approve(scene_id, version)

    def reject(self, scene_id: str, version: int) -> dict[str, Any]:
        return self.store.reject(scene_id, version)

    def select_version(self, scene_id: str, version: int) -> dict[str, Any]:
        return self.store.approve(scene_id, version)
