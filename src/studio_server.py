"""Local HTTP bridge for the AI Video Studio workspace.

The desktop shell can point its webview at this server.  It deliberately uses
only Python's standard library: projects and source media remain on the local
machine, and no request is sent to a cloud service by this module.
"""
from __future__ import annotations

import json
import hashlib
import re
import mimetypes
import threading
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from src.providers.voice.registry import ProviderRegistry
from src.services.import_service import ImportService
from src.services.script_service import ScriptService
from src.services.studio_project import LocalProjectManager
from src.services.voice_service import VoiceConfig, VoiceService
from src.video.scene_source_manager import SceneVideoStore


PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_UPLOAD_BYTES = 8 * 1024 * 1024 * 1024


class StudioApiError(ValueError):
    def __init__(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


class StudioApplication:
    """Small, testable local application boundary for the web UI."""

    def __init__(self, workspace_root: Path | str):
        self.workspace_root = Path(workspace_root).resolve()
        self.projects_root = self.workspace_root / "projects"
        self.manager = LocalProjectManager(self.workspace_root)

    @staticmethod
    def _project_id(value: str) -> str:
        if not PROJECT_ID.fullmatch(value):
            raise StudioApiError("Invalid project id.", HTTPStatus.NOT_FOUND)
        return value

    def _project_root(self, project_id: str) -> Path:
        identifier = self._project_id(project_id)
        root = self.projects_root / identifier
        if not root.is_dir():
            raise StudioApiError("Project not found.", HTTPStatus.NOT_FOUND)
        return root

    @staticmethod
    def _read_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
        if not path.is_file():
            return fallback or {}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _legacy_summary(self, root: Path) -> dict[str, Any]:
        remotion = self._read_json(root / "remotion.json")
        state = self._read_json(root / "project-state.json", {"status": "DRAFT"})
        return {
            "id": root.name,
            "name": remotion.get("name", root.name),
            "status": state.get("status", "DRAFT"),
            "source": {"imported": bool(remotion.get("scenes"))},
            "legacy": True,
            "updated_at": "",
        }

    def list_projects(self) -> list[dict[str, Any]]:
        known = {item["id"]: item for item in self.manager.list()}
        if self.projects_root.is_dir():
            for root in self.projects_root.iterdir():
                if root.is_dir() and PROJECT_ID.fullmatch(root.name) and (root / "remotion.json").is_file() and root.name not in known:
                    known[root.name] = self._legacy_summary(root)
        result: list[dict[str, Any]] = []
        for item in known.values():
            root = self.projects_root / item["id"]
            remotion = self._read_json(root / "remotion.json")
            result.append({
                "id": item["id"], "name": item.get("name", item["id"]), "status": item.get("status", "DRAFT"),
                "scene_count": len(remotion.get("scenes", [])), "imported": bool(item.get("source", {}).get("imported")),
                "legacy": bool(item.get("legacy", False)), "updated_at": item.get("updated_at", ""),
            })
        return sorted(result, key=lambda item: (not item["imported"], item["name"].lower()))

    def project(self, project_id: str) -> dict[str, Any]:
        root = self._project_root(project_id)
        remotion = self._read_json(root / "remotion.json")
        if not remotion:
            raise StudioApiError("Project configuration is missing.", HTTPStatus.CONFLICT)
        manifest = self._read_json(root / "project.json") or self._legacy_summary(root)
        state = self._read_json(root / "project-state.json", {"status": manifest.get("status", "DRAFT"), "history": []})
        scenes: list[dict[str, Any]] = []
        for scene in sorted(remotion.get("scenes", []), key=lambda item: int(item.get("index", 0))):
            scene_id = str(scene.get("id", ""))
            metadata = self._read_json(root / "scenes" / scene_id / "metadata.json")
            scenes.append({
                "id": scene_id,
                "number": int(scene.get("index", 0)),
                "narration": scene.get("narration", ""),
                "duration_in_frames": scene.get("durationInFrames", 0),
                "transition": scene.get("transition", "none"),
                "video": metadata,
            })
        script_path = root / "script" / "script.txt"
        if not script_path.is_file():
            script_path = root / "narration.json"
        report_relative = (manifest.get("source") or {}).get("last_import")
        report_path = (root / report_relative).resolve() if report_relative else None
        last_import_report = self._read_json(report_path) if report_path and report_path.is_relative_to(root) else {}
        return {
            "project": manifest,
            "workflow": state,
            "remotion": {key: remotion.get(key) for key in ("fps", "width", "height", "name")},
            "scenes": scenes,
            "script_text": script_path.read_text(encoding="utf-8") if script_path.suffix == ".txt" and script_path.is_file() else "",
            "last_import_report": last_import_report,
        }

    def create_project(self, name: str) -> dict[str, Any]:
        try:
            manifest = self.manager.create(name)
        except ValueError as exc:
            raise StudioApiError(str(exc)) from exc
        return self.project(str(manifest["id"]))

    def import_path(self, project_id: str, value: str) -> dict[str, Any]:
        path = Path(value).expanduser().resolve()
        service = ImportService(self.workspace_root, self._project_id(project_id))
        if path.is_file() and path.suffix.lower() == ".zip":
            return service.import_zip(path)
        if path.is_dir():
            return service.import_folder(path)
        raise StudioApiError("Choose a readable ZIP archive or a source folder.")

    def import_zip_upload(self, project_id: str, filename: str, content: bytes) -> dict[str, Any]:
        if not filename.lower().endswith(".zip"):
            raise StudioApiError("Only a .zip source archive can be uploaded here.")
        if not content or len(content) > MAX_UPLOAD_BYTES:
            raise StudioApiError("Invalid ZIP upload size.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        root = self._project_root(project_id)
        temporary = root / "source" / "imported" / f".incoming-{uuid.uuid4().hex}.zip.uploading"
        temporary.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(content)
        try:
            return self.import_uploaded_zip_file(project_id, filename, temporary)
        finally:
            temporary.unlink(missing_ok=True)

    def import_uploaded_zip_file(self, project_id: str, filename: str, temporary: Path) -> dict[str, Any]:
        """Atomically store a streamed ZIP upload before validating/importing it."""

        if not filename.lower().endswith(".zip"):
            raise StudioApiError("Only a .zip source archive can be uploaded here.")
        root = self._project_root(project_id)
        safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(filename).name).strip(". ") or "source.zip"
        destination_root = root / "source" / "imported"
        destination_root.mkdir(parents=True, exist_ok=True)
        manifest = self._read_json(root / "project.json")
        report_relative = (manifest.get("source") or {}).get("last_import")
        report_path = (root / report_relative).resolve() if report_relative else None
        if report_path and report_path.is_relative_to(root) and report_path.is_file():
            previous = self._read_json(report_path)
            previous_archive = destination_root / Path(str(previous.get("source", ""))).name
            if previous.get("valid_files", 0) > 0 and not previous.get("invalid_files") and previous_archive.is_file():
                if previous_archive.stat().st_size == temporary.stat().st_size and self._sha256(previous_archive) == self._sha256(temporary):
                    temporary.unlink()
                    return {**previous, "reused_import": True}
        target = destination_root / safe_name
        suffix = 2
        while target.exists():
            target = target.with_name(f"{target.stem}-{suffix}{target.suffix}")
            suffix += 1
        temporary.replace(target)
        return ImportService(self.workspace_root, self._project_id(project_id)).import_zip(target)

    def save_script(self, project_id: str, text: str) -> dict[str, Any]:
        if not isinstance(text, str):
            raise StudioApiError("Script text must be a string.")
        return ScriptService(self.workspace_root, self._project_id(project_id)).save_bulk(text)

    def approve_script(self, project_id: str) -> dict[str, Any]:
        try:
            return ScriptService(self.workspace_root, self._project_id(project_id)).approve_mapping()
        except ValueError as exc:
            raise StudioApiError(str(exc), HTTPStatus.CONFLICT) from exc

    def set_video_status(self, project_id: str, scene_id: str, version: int, status: str) -> dict[str, Any]:
        store = SceneVideoStore(self.workspace_root, self._project_id(project_id))
        if status == "approved":
            return store.approve(scene_id, version)
        if status == "rejected":
            return store.reject(scene_id, version)
        raise StudioApiError("Video status must be approved or rejected.")

    def source_video_path(self, project_id: str, scene_id: str) -> Path:
        root = self._project_root(project_id)
        if not PROJECT_ID.fullmatch(scene_id):
            raise StudioApiError("Invalid scene id.", HTTPStatus.NOT_FOUND)
        metadata = self._read_json(root / "scenes" / scene_id / "metadata.json")
        active = metadata.get("active_version")
        record = next((item for item in metadata.get("versions", []) if item.get("version") == active), None)
        relative = record.get("source_video") if record else None
        source = (root / relative).resolve() if relative else None
        if not source or not source.is_relative_to(root) or not source.is_file():
            raise StudioApiError("Scene source video is unavailable.", HTTPStatus.NOT_FOUND)
        return source

    def update_voice(self, project_id: str, request: dict[str, Any]) -> dict[str, Any]:
        """Persist only controls that the active provider actually reports."""

        identifier = self._project_id(project_id)
        manifest = self.manager.load(identifier)
        provider = ProviderRegistry().get("omnivoice")
        capabilities = provider.capabilities()
        mode = str(request.get("mode", manifest.get("voice", {}).get("mode", "voice_design")))
        if mode not in capabilities.get("modes", ["auto"]):
            raise StudioApiError(f"OmniVoice does not support mode '{mode}'.", HTTPStatus.CONFLICT)
        speed = float(request.get("speed", manifest.get("voice", {}).get("speed", 1.10)))
        speed_range = capabilities.get("speed_range", {"min": 0.85, "max": 1.20})
        if not float(speed_range["min"]) <= speed <= float(speed_range["max"]):
            raise StudioApiError(f"Voice speed must be {speed_range['min']:.2f}–{speed_range['max']:.2f}.")
        design = dict(manifest.get("voice", {}).get("design") or {})
        if mode == "voice_design":
            gender = str(request.get("gender", design.get("gender", "male")))
            pitch = str(request.get("pitch", design.get("pitch", "moderate")))
            age = str(request.get("age", design.get("age", "young adult")))
            if gender not in {"male", "female"} or not capabilities.get("gender"):
                raise StudioApiError("The active provider cannot apply that gender setting.")
            if pitch not in {"low", "moderate", "high"} or not capabilities.get("pitch"):
                raise StudioApiError("The active provider cannot apply that pitch setting.")
            if age not in {"young adult", "middle-aged", "older adult"} or not capabilities.get("age"):
                raise StudioApiError("The active provider cannot apply that age setting.")
            design = {"gender": gender, "age": age, "pitch": pitch}
        else:
            design = {}
        manifest["voice"] = {
            **dict(manifest.get("voice") or {}), "provider": "omnivoice", "mode": mode,
            "language": str(request.get("language", "vi")), "design": design,
            "speed": round(speed, 2), "approved": False, "selected_preview": None, "preview_file": None,
        }
        return self.manager.save(identifier, manifest)

    def generate_voice_preview(self, project_id: str, request: dict[str, Any]) -> dict[str, Any]:
        text = str(request.get("text", "")).strip()
        if not text:
            raise StudioApiError("Enter preview text before generating voice.")
        if len(text) > 1_000:
            raise StudioApiError("Voice preview text must be 1,000 characters or fewer.")
        manifest = self.update_voice(project_id, request)
        config = VoiceConfig.from_project(manifest)
        # A manual preview favors responsiveness. Full narration keeps the
        # provider's 16-step default and therefore has a distinct cache key.
        config.options = {**config.options, "num_step": 4}
        service = VoiceService(self._project_root(project_id), fallback=False)
        try:
            result = service.generate_voice_preview(config, text)
        except (RuntimeError, KeyError) as exc:
            raise StudioApiError(str(exc), HTTPStatus.CONFLICT) from exc
        preview = Path(result.audio_file).resolve()
        root = self._project_root(project_id)
        if not preview.is_relative_to(root):
            raise StudioApiError("Generated preview path escaped the project.", HTTPStatus.INTERNAL_SERVER_ERROR)
        manifest = self.manager.load(project_id)
        preview_id = preview.stem
        manifest["voice"] = {
            **dict(manifest.get("voice") or {}), "preview_file": preview.relative_to(root).as_posix(),
            "selected_preview": preview_id, "approved": False,
        }
        self.manager.save(project_id, manifest)
        return {
            **result.to_dict(), "preview_id": preview_id,
            "audio_url": f"/api/projects/{project_id}/voice/preview", "metrics": service.last_metrics,
        }

    def voice_preview_path(self, project_id: str) -> Path:
        root = self._project_root(project_id)
        manifest = self.manager.load(project_id)
        relative = (manifest.get("voice") or {}).get("preview_file")
        path = (root / relative).resolve() if relative else None
        if not path or not path.is_relative_to(root) or not path.is_file():
            raise StudioApiError("Generate a voice preview first.", HTTPStatus.NOT_FOUND)
        return path

    def approve_voice(self, project_id: str) -> dict[str, Any]:
        self.voice_preview_path(project_id)
        manifest = self.manager.load(project_id)
        voice = dict(manifest.get("voice") or {})
        if not voice.get("selected_preview"):
            raise StudioApiError("Generate and listen to a preview before approving voice.", HTTPStatus.CONFLICT)
        voice["approved"] = True
        manifest["voice"] = voice
        manifest["status"] = "READY_TO_RENDER"
        return self.manager.save(project_id, manifest)

    def edit_video(self, project_id: str, scene_id: str, request: dict[str, Any]) -> dict[str, Any]:
        """Apply one non-destructive edit to an imported source version."""

        store = SceneVideoStore(self.workspace_root, self._project_id(project_id))
        version = int(request.get("version", 0))
        action = str(request.get("action", ""))
        if action == "speed":
            return store.set_playback_speed(scene_id, version, float(request.get("speed")))
        if action == "hold_last_frame":
            return store.set_hold_last_frame(scene_id, version, bool(request.get("enabled")))
        if action == "trim":
            return store.set_trim(scene_id, version, float(request.get("start")), float(request.get("end")))
        if action == "crop":
            return store.set_crop(scene_id, version, float(request.get("x", 0.5)), float(request.get("y", 0.5)), str(request.get("mode", "cover")))
        if action == "source_audio":
            return store.set_source_audio(
                scene_id, version, str(request.get("mode", "mute")), request.get("volume"), request.get("duck"),
                request.get("fade_in"), request.get("fade_out"),
            )
        if action == "transition":
            return store.set_transition(scene_id, str(request.get("transition", "none")))
        raise StudioApiError("Unsupported video edit.")

    def voice_catalog(self) -> dict[str, Any]:
        registry = ProviderRegistry()
        return {"active_provider": "omnivoice", "providers": registry.catalog(check_health=True)}


class StudioRequestHandler(SimpleHTTPRequestHandler):
    """Serve the static desktop UI and a narrowly scoped local JSON API."""

    app: StudioApplication

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _video(self, path: Path) -> None:
        size = path.stat().st_size
        start, end = 0, size - 1
        range_header = self.headers.get("Range")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if not match or not size or (not match.group(1) and not match.group(2)):
                raise StudioApiError("Invalid video byte range.", HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            if match.group(1):
                start = int(match.group(1))
                end = min(int(match.group(2)), size - 1) if match.group(2) else size - 1
            else:
                start = max(0, size - int(match.group(2)))
            if start > end or start >= size:
                raise StudioApiError("Video byte range is outside the file.", HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
        self.send_response(HTTPStatus.PARTIAL_CONTENT if range_header else HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if range_header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with path.open("rb") as source:
                source.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Browser stopped playback or switched to another scene.

    def _body_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 2 * 1024 * 1024:
            raise StudioApiError("Invalid JSON request size.")
        try:
            decoded = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StudioApiError("Request body must be valid UTF-8 JSON.") from exc
        if not isinstance(decoded, dict):
            raise StudioApiError("JSON request must be an object.")
        return decoded

    @staticmethod
    def _parts(path: str) -> list[str]:
        return [part for part in path.split("/") if part]

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        parts = self._parts(unquote(parsed.path))
        try:
            if parts == ["api", "health"]:
                self._json(HTTPStatus.OK, {"ok": True, "voice": self.app.voice_catalog()})
                return
            if parts == ["api", "projects"]:
                self._json(HTTPStatus.OK, {"projects": self.app.list_projects()})
                return
            if len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3:] == ["voice", "preview"]:
                self._video(self.app.voice_preview_path(parts[2]))
                return
            if len(parts) == 6 and parts[:2] == ["api", "projects"] and parts[3] == "scenes" and parts[5] == "source":
                self._video(self.app.source_video_path(parts[2], parts[4]))
                return
            if len(parts) == 3 and parts[:2] == ["api", "projects"]:
                self._json(HTTPStatus.OK, self.app.project(parts[2]))
                return
            super().do_GET()
        except StudioApiError as exc:
            self._json(exc.status, {"error": str(exc)})
        except Exception as exc:  # keep local UI errors readable without leaking a traceback
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        parts = self._parts(unquote(urlparse(self.path).path))
        try:
            if parts == ["api", "projects"]:
                body = self._body_json()
                self._json(HTTPStatus.CREATED, self.app.create_project(str(body.get("name", ""))))
                return
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "import-path":
                body = self._body_json()
                self._json(HTTPStatus.OK, self.app.import_path(parts[2], str(body.get("path", ""))))
                return
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "import-zip":
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_UPLOAD_BYTES:
                    raise StudioApiError("Invalid ZIP upload size.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                filename = unquote(self.headers.get("X-File-Name", "source.zip"))
                root = self.app._project_root(parts[2])
                temporary = root / "source" / "imported" / f".incoming-{uuid.uuid4().hex}.zip.uploading"
                temporary.parent.mkdir(parents=True, exist_ok=True)
                try:
                    remaining = length
                    with temporary.open("wb") as target:
                        while remaining:
                            chunk = self.rfile.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise StudioApiError("ZIP upload ended before Content-Length was received.")
                            target.write(chunk)
                            remaining -= len(chunk)
                    self._json(HTTPStatus.OK, self.app.import_uploaded_zip_file(parts[2], filename, temporary))
                finally:
                    temporary.unlink(missing_ok=True)
                return
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "script":
                body = self._body_json()
                self._json(HTTPStatus.OK, self.app.save_script(parts[2], body.get("text", "")))
                return
            if len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3:] == ["script", "approve"]:
                self._json(HTTPStatus.OK, self.app.approve_script(parts[2]))
                return
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "voice":
                self._json(HTTPStatus.OK, self.app.update_voice(parts[2], self._body_json()))
                return
            if len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3:] == ["voice", "preview"]:
                self._json(HTTPStatus.OK, self.app.generate_voice_preview(parts[2], self._body_json()))
                return
            if len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3:] == ["voice", "approve"]:
                self._json(HTTPStatus.OK, self.app.approve_voice(parts[2]))
                return
            if len(parts) == 6 and parts[:2] == ["api", "projects"] and parts[3] == "scenes" and parts[5] == "video":
                body = self._body_json()
                self._json(HTTPStatus.OK, self.app.set_video_status(parts[2], parts[4], int(body.get("version", 0)), str(body.get("status", ""))))
                return
            if len(parts) == 7 and parts[:2] == ["api", "projects"] and parts[3] == "scenes" and parts[5:] == ["video", "edit"]:
                self._json(HTTPStatus.OK, self.app.edit_video(parts[2], parts[4], self._body_json()))
                return
            raise StudioApiError("Unknown API route.", HTTPStatus.NOT_FOUND)
        except StudioApiError as exc:
            self._json(exc.status, {"error": str(exc)})
        except (ValueError, FileNotFoundError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})


def serve_studio(workspace_root: Path | str, ui_root: Path | str, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the local studio server until interrupted."""

    app = StudioApplication(workspace_root)
    directory = str(Path(ui_root).resolve())

    class Handler(StudioRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, directory=directory, **kwargs)

    Handler.app = app
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"AI Video Studio local server: http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def run_server_in_thread(workspace_root: Path | str, ui_root: Path | str) -> tuple[ThreadingHTTPServer, threading.Thread]:
    """Test helper: start a loopback server on an ephemeral port."""

    app = StudioApplication(workspace_root)
    directory = str(Path(ui_root).resolve())

    class Handler(StudioRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, directory=directory, **kwargs)

    Handler.app = app
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
