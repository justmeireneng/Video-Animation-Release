from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from src.services.project_state import ProjectStateService
from src.services.scene_mapper import SceneMapper
from src.services.studio_project import LocalProjectManager
from src.video.scene_source_manager import SceneVideoStore


MAX_ZIP_MEMBERS = 10_000
MAX_ZIP_UNCOMPRESSED_BYTES = 8 * 1024 * 1024 * 1024


class ImportService:
    def __init__(self, repo_root: Path | str, project_name: str,
                 prober: Callable[[Path, Path], dict[str, Any]] | None = None):
        self.repo_root = Path(repo_root).resolve()
        self.project_name = project_name
        self.store = SceneVideoStore(self.repo_root, project_name, prober=prober) if prober else SceneVideoStore(self.repo_root, project_name)
        self.project_root = self.store.project_root
        self.state = ProjectStateService(self.project_root)
        self.projects = LocalProjectManager(self.repo_root)

    def import_zip(self, zip_path: Path | str) -> dict[str, Any]:
        archive = Path(zip_path).resolve()
        if not archive.is_file() or not zipfile.is_zipfile(archive):
            raise ValueError(f"Not a readable ZIP archive: {archive}")
        self.state.set("UPLOADED", archive.name)
        with tempfile.TemporaryDirectory(prefix="flow-import-") as temp:
            root = Path(temp)
            original_names: dict[Path, str] = {}
            with zipfile.ZipFile(archive) as package:
                members = package.infolist()
                if len(members) > MAX_ZIP_MEMBERS:
                    raise ValueError(f"ZIP has too many entries ({len(members)} > {MAX_ZIP_MEMBERS}).")
                total_size = sum(member.file_size for member in members)
                if total_size > MAX_ZIP_UNCOMPRESSED_BYTES:
                    raise ValueError("ZIP uncompressed size exceeds the local import safety limit.")
                for index, member in enumerate(members, 1):
                    if member.flag_bits & 0x1:
                        raise ValueError(f"Encrypted ZIP entries are not supported: {member.filename}")
                    destination = self._safe_zip_destination(root, member.filename, index)
                    if member.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with package.open(member) as source, destination.open("wb") as target:
                        shutil.copyfileobj(source, target)
                    original_names[destination.resolve()] = PurePosixPath(member.filename).name
            return self._import_folder(root, source_label=archive.name, original_names=original_names)

    @staticmethod
    def _safe_zip_destination(root: Path, member_name: str, index: int) -> Path:
        member = PurePosixPath(member_name.replace("\\", "/"))
        if member.is_absolute() or ".." in member.parts:
            raise ValueError(f"Unsafe ZIP member: {member_name}")
        parts = [re.sub(r'[<>:"|?*\x00-\x1f]', "_", part).rstrip(". ") or "_" for part in member.parts]
        destination = (root.joinpath(*parts)).resolve()
        if not destination.is_relative_to(root.resolve()):
            raise ValueError(f"Unsafe ZIP member: {member_name}")
        if destination.exists() and not member_name.endswith("/"):
            destination = destination.with_stem(f"{destination.stem}__zip_{index}")
        return destination

    def import_folder(self, folder_path: Path | str) -> dict[str, Any]:
        folder = Path(folder_path).resolve()
        if not folder.is_dir():
            raise FileNotFoundError(folder)
        self.state.set("UPLOADED", folder.name)
        return self._import_folder(folder, source_label=folder.name)

    def _import_folder(self, folder: Path, source_label: str,
                       original_names: dict[Path, str] | None = None) -> dict[str, Any]:
        found, unmatched = SceneMapper.scan(folder)
        project = json.loads(self.store.remotion_path.read_text(encoding="utf-8"))
        # New desktop projects start without pre-authored scene slots.  Build
        # those slots directly from the numeric Flow filenames, preserving
        # gaps so the user can review missing source scenes explicitly.
        if (self.project_root / "project.json").is_file() and found:
            project = self.projects.ensure_scene_slots(self.project_name, [item.number for item in found])
        mapping = SceneMapper.scene_map(project)
        counts = Counter(item.number for item in found)
        records: list[dict[str, Any]] = []
        invalid: list[dict[str, str]] = []
        warnings: list[str] = [f"Unmatched filename: {path.name}" for path in unmatched]
        mapped_numbers: set[int] = set()
        for item in found:
            scene_id = mapping.get(item.number)
            if scene_id is None:
                warnings.append(f"Scene_{item.number} does not exist in this project.")
                continue
            mapped_numbers.add(item.number)
            record = self.store.import_video(
                scene_id,
                item.path,
                provider="google_flow_manual",
                source_filename=(original_names or {}).get(item.path.resolve(), item.path.name),
            )
            records.append({"scene_number": item.number, "scene_id": scene_id, **record})
            if record["status"] == "invalid":
                invalid.append({"scene_id": scene_id, "file": item.path.name, "error": record.get("error", "invalid media")})
        missing = [scene_id for number, scene_id in sorted(mapping.items()) if number not in mapped_numbers]
        report = {
            "source": source_label,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files_found": len(found) + len(unmatched),
            "valid_files": sum(1 for item in records if item["status"] != "invalid"),
            "invalid_files": invalid,
            "mapped_scenes": sorted({item["scene_id"] for item in records}),
            "duplicate_scenes": {f"scene_{number:02d}": count for number, count in counts.items() if count > 1},
            "missing_scenes": missing,
            "warnings": warnings,
            "scene_map": records,
            "render_readiness": {
                "approved": sum(1 for item in records if item["status"] == "approved"),
                "pending_review": sum(1 for item in records if item["status"] == "pending_review"),
                "missing": len(missing),
                "invalid": len(invalid),
            },
            "source_audio": [
                {
                    "scene_id": item["scene_id"],
                    "version": item["version"],
                    "has_audio": item["probe"].get("has_audio", False),
                    **item["source_audio"],
                }
                for item in records
            ],
        }
        imports = self.project_root / "imports"
        imports.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        report_path = imports / f"import-{stamp}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["report_path"] = str(report_path)
        self.state.set("MAPPED", f"Imported {len(records)} source versions")
        self.state.set("READY" if records and not invalid else "NEEDS_CHANGES", "Review pending source versions")
        if (self.project_root / "project.json").is_file():
            manifest = self.projects.load(self.project_name)
            manifest["source"] = {
                **dict(manifest.get("source") or {}),
                "imported": bool(records),
                "last_import": report_path.relative_to(self.project_root).as_posix(),
                "scene_count": len(mapping),
            }
            manifest["status"] = "SCRIPT_MAPPING" if records else "NEEDS_CHANGES"
            self.projects.save(self.project_name, manifest)
        return report
