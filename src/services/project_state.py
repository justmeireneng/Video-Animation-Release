from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProjectStateService:
    STATES = {
        "DRAFT", "UPLOADED", "MAPPED", "SCRIPT_MAPPING", "VOICE_SETUP", "READY_TO_RENDER",
        "READY", "RENDERING", "REVIEW", "POST_RENDER_REVIEW", "APPROVED", "NEEDS_CHANGES", "DONE",
    }

    def __init__(self, project_root: Path | str):
        self.project_root = Path(project_root).resolve()
        self.path = self.project_root / "project-state.json"

    def get(self) -> dict[str, Any]:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"status": "DRAFT", "history": []}

    def set(self, status: str, note: str = "") -> dict[str, Any]:
        if status not in self.STATES:
            raise ValueError(f"Invalid project state: {status}")
        data = self.get()
        event = {"status": status, "at": datetime.now(timezone.utc).isoformat(), "note": note}
        data["status"] = status
        data.setdefault("history", []).append(event)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return data
