#!/usr/bin/env python3
"""Small dependency-free browser UI for scene-video review checkpoints."""
from __future__ import annotations

import html
import json
import tempfile
import webbrowser
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from src.video.scene_source_manager import SceneVideoStore


def _page(store: SceneVideoStore, scene_id: str, selected: int | None = None, message: str = "") -> str:
    data = store.load_metadata(scene_id)
    versions = data.get("versions", [])
    if selected is None:
        selected = data.get("active_version")
    record = next((item for item in versions if item["version"] == selected), None)
    options = "".join(
        f'<option value="{item["version"]}" {"selected" if item["version"] == selected else ""}>'
        f'v{item["version"]} · {html.escape(item["source_provider"])} · {item["status"]}</option>'
        for item in versions
    )
    video = (
        f'<video controls muted preload="metadata" src="/media?version={record["version"]}"></video>'
        if record else '<div class="empty">No source clip imported</div>'
    )
    details = json.dumps(record or {}, ensure_ascii=False, indent=2)
    refs = ""
    version_value = record["version"] if record else 1
    trim = record.get("trim", {"start": 0, "end": data.get("duration", 0)}) if record else {"start": 0, "end": data.get("duration", 0)}
    if trim.get("end") is None:
        trim = {**trim, "end": record.get("probe", {}).get("duration", data.get("duration", 0)) if record else data.get("duration", 0)}
    crop = record.get("crop", {"mode": "cover", "x": 0.5, "y": 0.5}) if record else {"mode": "cover", "x": 0.5, "y": 0.5}
    source_audio = record.get("source_audio", {"mode": "background", "enabled": True, "volume": 0.30, "duck_under_narration": True, "fade_in": 0.15, "fade_out": 0.20}) if record else {"mode": "background", "enabled": True, "volume": 0.30, "duck_under_narration": True, "fade_in": 0.15, "fade_out": 0.20}
    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(scene_id)} video review</title>
<style>
body{{margin:0;background:#0f1b2d;color:#edf4ff;font:16px 'Segoe UI',sans-serif}}main{{max-width:1180px;margin:auto;padding:28px}}
.grid{{display:grid;grid-template-columns:1.2fr .8fr;gap:22px}}.card{{background:#17263b;border:1px solid #30445f;border-radius:18px;padding:20px}}
video{{width:100%;max-height:620px;background:#060b12;border-radius:14px}}h1,h2{{margin-top:0}}label{{display:block;margin:10px 0 5px;color:#bcd0e8}}
input,select,button,a.button{{box-sizing:border-box;border:1px solid #58708e;border-radius:9px;padding:10px;background:#0f1b2d;color:white}}
button,a.button{{cursor:pointer;background:#245c91;text-decoration:none;display:inline-block}}button.reject{{background:#873e4a}}form{{margin:12px 0}}.row{{display:flex;gap:8px;flex-wrap:wrap}}
pre{{white-space:pre-wrap;max-height:360px;overflow:auto;background:#0b1422;padding:14px;border-radius:10px}}code{{color:#7ee0ee}}.message{{color:#ffcc68}}.empty{{padding:100px;text-align:center;background:#0b1422;border-radius:14px}}
@media(max-width:850px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>{html.escape(scene_id)} · Source Video Review</h1><p class="message">{html.escape(message)}</p>
<div class="grid"><section class="card"><h2>Current source clip</h2>
<form method="get"><label>Compare / choose version</label><select name="version" onchange="this.form.submit()">{options}</select></form>{video}
<div class="row"><form method="post" action="/action"><input type="hidden" name="action" value="approve"><input type="hidden" name="version" value="{version_value}"><button>Approve Video</button></form>
<form method="post" action="/action"><input type="hidden" name="action" value="reject"><input type="hidden" name="version" value="{version_value}"><button class="reject">Reject Video</button></form>
<a class="button" href="http://127.0.0.1:3000/TikTokExplainer" target="_blank">Preview in Timeline</a></div>
<form method="post" action="/import" enctype="multipart/form-data"><label>Import New Version</label><div class="row"><input type="file" name="clip" accept="video/*" required><select name="provider"><option value="google_flow_manual">Google Flow manual</option><option value="generated_video">Generated video</option><option value="existing_video">Existing video</option></select><button>Import</button></div></form>
</section><aside class="card"><h2>Scene card</h2><p><b>Narration</b><br>{html.escape(data.get("narration", ""))}</p>
<p><b>Source filename</b><br><code>{html.escape(str(record.get("source_filename", "") if record else ""))}</code></p><p><b>Provider</b>: {html.escape(str(record.get("source_provider", "") if record else ""))}<br><b>Status</b>: {html.escape(str(record.get("status", "missing") if record else "missing"))}<br><b>Duration</b>: {record.get("probe", {}).get("duration", 0) if record else 0}s</p><ul>{refs}</ul>
<form method="post" action="/action"><input type="hidden" name="action" value="trim"><input type="hidden" name="version" value="{version_value}"><label>Trim Clip</label><div class="row"><input name="start" type="number" step="0.01" value="{trim['start']}"><input name="end" type="number" step="0.01" value="{trim['end']}"><button>Set Trim</button></div></form>
<form method="post" action="/action"><input type="hidden" name="action" value="crop"><input type="hidden" name="version" value="{version_value}"><label>Set Crop</label><div class="row"><select name="mode"><option {"selected" if crop['mode']=="cover" else ""}>cover</option><option {"selected" if crop['mode']=="contain" else ""}>contain</option></select><input name="x" type="number" min="0" max="1" step="0.01" value="{crop['x']}"><input name="y" type="number" min="0" max="1" step="0.01" value="{crop['y']}"><button>Set Crop</button></div></form>
<form method="post" action="/action"><input type="hidden" name="action" value="audio"><input type="hidden" name="version" value="{version_value}"><label>Source Audio</label><div class="row"><select name="mode"><option {"selected" if source_audio['mode']=="mute" else ""}>mute</option><option {"selected" if source_audio['mode']=="background" else ""}>background</option><option {"selected" if source_audio['mode']=="full" else ""}>full</option></select><input name="volume" type="number" min="0" max="1" step="0.05" value="{source_audio['volume']}"><select name="duck"><option value="true" {"selected" if source_audio['duck_under_narration'] else ""}>duck under narration</option><option value="false" {"selected" if not source_audio['duck_under_narration'] else ""}>no ducking</option></select><button>Set Audio</button></div></form>
<pre>{html.escape(details)}</pre></aside></div></main></body></html>"""


def serve_scene_video_review(store: SceneVideoStore, scene_id: str, port: int = 8811, open_browser: bool = True) -> None:
    store.load_metadata(scene_id)

    class Handler(BaseHTTPRequestHandler):
        def _redirect(self, message: str = "") -> None:
            self.send_response(303)
            self.send_header("Location", "/?" + urlencode({"message": message}))
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/media":
                try:
                    version = int(query.get("version", ["0"])[0])
                    data = store.load_metadata(scene_id)
                    record = store._version(data, version)
                    media = (store.project_root / record["source_video"]).resolve()
                    if not media.is_relative_to(store.project_root) or not media.is_file():
                        raise FileNotFoundError(media)
                    size = media.stat().st_size
                    start, end = 0, size - 1
                    range_header = self.headers.get("Range")
                    if range_header and range_header.startswith("bytes="):
                        values = range_header[6:].split("-", 1)
                        start = int(values[0] or 0)
                        end = min(int(values[1]) if values[1] else size - 1, size - 1)
                        self.send_response(206)
                        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                    else:
                        self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(end - start + 1))
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    with media.open("rb") as handle:
                        handle.seek(start)
                        self.wfile.write(handle.read(end - start + 1))
                except Exception as exc:  # pragma: no cover - browser error path
                    self.send_error(404, str(exc))
                return
            selected = int(query["version"][0]) if query.get("version") else None
            page = _page(store, scene_id, selected, query.get("message", [""])[0]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def do_POST(self) -> None:  # noqa: N802
            try:
                if self.path == "/import":
                    length = int(self.headers.get("Content-Length", "0"))
                    body = self.rfile.read(length)
                    envelope = (
                        f"Content-Type: {self.headers['Content-Type']}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
                    )
                    message = BytesParser(policy=default).parsebytes(envelope)
                    fields = {part.get_param("name", header="content-disposition"): part for part in message.iter_parts()}
                    clip = fields["clip"]
                    provider = fields["provider"].get_content().strip()
                    suffix = Path(clip.get_filename() or "clip.mp4").suffix or ".mp4"
                    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                        handle.write(clip.get_payload(decode=True))
                        temp_path = Path(handle.name)
                    try:
                        record = store.import_video(scene_id, temp_path, provider)
                    finally:
                        temp_path.unlink(missing_ok=True)
                    self._redirect(f"Imported v{record['version']}; review is pending.")
                    return
                length = int(self.headers.get("Content-Length", "0"))
                values = {key: item[0] for key, item in parse_qs(self.rfile.read(length).decode("utf-8")).items()}
                action, version = values["action"], int(values["version"])
                if action == "approve":
                    store.approve(scene_id, version)
                elif action == "reject":
                    store.reject(scene_id, version)
                elif action == "trim":
                    store.set_trim(scene_id, version, float(values["start"]), float(values["end"]))
                elif action == "crop":
                    store.set_crop(scene_id, version, float(values["x"]), float(values["y"]), values["mode"])
                elif action == "audio":
                    store.set_source_audio(scene_id, version, values["mode"], float(values["volume"]), values["duck"] == "true")
                self._redirect(f"Updated v{version}: {action}.")
            except Exception as exc:  # pragma: no cover - browser error path
                self._redirect(f"Error: {exc}")

        def log_message(self, format: str, *args: object) -> None:
            return

    url = f"http://127.0.0.1:{port}/"
    print(f"Scene video review UI: {url}")
    if open_browser:
        webbrowser.open(url)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
