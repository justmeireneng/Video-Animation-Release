#!/usr/bin/env python3
"""Dependency-free voice control and audio comparison panel."""
from __future__ import annotations

import html
import json
import tempfile
import webbrowser
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from src.services.voice_control import VoiceControlService


def _form_text(part: Any) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    return payload.decode(part.get_content_charset() or "utf-8").strip()


def _manifest(control: VoiceControlService) -> list[dict]:
    path = control.preview_root / "manifest.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("previews", [])


def voice_control_page(control: VoiceControlService, message: str = "") -> str:
    contract = control.ui_contract()
    state = contract["state"]
    providers = contract["providers"]
    active = next((item for item in providers if item["provider_id"] == state["voiceProvider"]), providers[0])
    caps = active["capabilities"]
    provider_options = "".join(
        f'<option value="{html.escape(item["provider_id"])}" '
        f'{"selected" if item["provider_id"] == state["voiceProvider"] else ""} '
        f'{"" if item["available"] else "disabled"}>{html.escape(item["display_name"])}'
        f'{"" if item["available"] else " — Not Available"}</option>'
        for item in providers
    )
    mode_options = "".join(
        f'<option value="{mode}" {"selected" if mode == state["voiceMode"] else ""}>'
        f'{mode.replace("_", " ").title()}</option>' for mode in caps.get("modes", ["auto"])
    )
    voice_options = '<option value="">Provider default</option>' + "".join(
        f'<option value="{html.escape(str(item.get("voice_id", "")))}" '
        f'{"selected" if str(item.get("voice_id")) == str(state.get("voiceId")) else ""}>'
        f'{html.escape(str(item.get("name") or item.get("voice_id")))}</option>'
        for item in active.get("voices", [])
    )
    profile_options = '<option value="">No reusable profile</option>' + "".join(
        f'<option value="{html.escape(item["profile_id"])}">{html.escape(item["name"])}</option>'
        for item in contract.get("profiles", [])
    )
    cards = "".join(
        f'''<article class="preview-card {"selected" if item["preview_id"] == state.get("selectedPreview") else ""}">
        <h3>{html.escape(item["preview_id"].replace("_", " · "))}x</h3>
        <p>{item["duration"]:.3f}s · {item["sample_rate"]} Hz</p>
        <audio controls preload="metadata" src="/audio?name={html.escape(Path(item["file"]).name)}"></audio>
        <form method="post" action="/select"><input type="hidden" name="preview" value="{html.escape(item["preview_id"])}"><button>Select this voice</button></form>
        </article>''' for item in _manifest(control)
    ) or '<p class="muted">Run “Generate 4 comparisons” to create A/B audio.</p>'
    contract_json = json.dumps(contract, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voice Control · {html.escape(control.project_root.name)}</title><style>
body{{margin:0;background:#0d1524;color:#edf4ff;font:15px Segoe UI,sans-serif}}main{{max-width:1120px;margin:auto;padding:28px}}h1{{margin:0 0 8px}}h2{{margin-top:0}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}.card{{background:#17253a;border:1px solid #30445f;border-radius:18px;padding:20px}}label{{display:block;color:#bcd0e8;margin:13px 0 6px}}
select,input,textarea,button{{box-sizing:border-box;width:100%;border:1px solid #58708e;border-radius:9px;padding:10px;background:#0f1b2d;color:white}}textarea{{min-height:105px;resize:vertical}}button{{cursor:pointer;background:#24669e;font-weight:600}}button.secondary{{background:#37506c}}audio{{width:100%;margin:8px 0}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.previews{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.preview-card{{padding:14px;border:1px solid #3c536f;border-radius:12px;background:#101d30}}.preview-card.selected{{border-color:#65d7a8;box-shadow:0 0 0 2px #65d7a833}}.message{{color:#ffd477;min-height:22px}}.muted{{color:#93a9c3}}.hidden{{display:none}}.status{{padding:8px 12px;border-radius:999px;background:#253c58;display:inline-block}}
@media(max-width:800px){{.grid,.previews{{grid-template-columns:1fr}}}}</style></head><body><main>
<h1>VOICE · {html.escape(control.project_root.name)}</h1><p class="muted">Choose and preview voice only. No video render is triggered here.</p><p class="message">{html.escape(message)}</p>
<div class="grid"><section class="card"><h2>Voice controls</h2><form method="post" action="/generate" enctype="multipart/form-data" accept-charset="UTF-8" id="voice-form">
<label>Provider</label><select name="provider" id="provider">{provider_options}</select>
<label>Mode</label><select name="mode" id="mode">{mode_options}</select>
<div id="gender-wrap" class="{"" if state["voiceMode"]=="voice_design" and caps.get("gender") else "hidden"}"><label>Gender</label><div class="row"><label><input type="radio" name="gender" value="male" {"checked" if state["gender"]=="male" else ""}> Male</label><label><input type="radio" name="gender" value="female" {"checked" if state["gender"]=="female" else ""}> Female</label></div></div>
<div id="age-wrap" class="{"" if state["voiceMode"]=="voice_design" and caps.get("age") else "hidden"}"><label>Age</label><select name="age" id="age"><option {"selected" if state["age"]=="young adult" else ""}>young adult</option><option {"selected" if state["age"]=="middle-aged" else ""}>middle-aged</option><option {"selected" if state["age"]=="older adult" else ""}>older adult</option></select></div>
<div id="pitch-wrap" class="{"" if state["voiceMode"]=="voice_design" and caps.get("pitch") else "hidden"}"><label>Pitch</label><select name="pitch" id="pitch"><option value="low" {"selected" if state["pitch"]=="low" else ""}>Low</option><option value="moderate" {"selected" if state["pitch"]=="moderate" else ""}>Moderate</option><option value="high" {"selected" if state["pitch"]=="high" else ""}>High</option></select></div>
<label>Speed · <span id="speed-label">{float(state["speed"]):.2f}x</span></label><input type="range" name="speed" id="speed" min="0.85" max="1.20" step="0.01" value="{float(state["speed"]):.2f}">
<label>Voice profile</label><select id="profile">{profile_options}</select><label>Provider voice</label><select name="voice_id" id="voice-id">{voice_options}</select>
<div id="reference-wrap" class="{"" if state["voiceMode"]=="voice_clone" and caps.get("reference_audio") else "hidden"}"><label>Clone reference audio</label><input type="file" name="reference_audio" accept="audio/*"></div>
<label>Preview text</label><textarea name="preview_text">{html.escape(state["previewText"])}</textarea><button>Generate Preview</button></form>
<form method="post" action="/comparisons"><button class="secondary">Generate 4 comparisons</button></form></section>
<section class="card"><h2>Preview & selection</h2><span class="status">{html.escape(state["previewStatus"])}</span>
<audio id="active-preview" controls {"autoplay" if state.get("previewFile") else ""} {f'src="/audio?name={html.escape(Path(state["previewFile"]).name)}"' if state.get("previewFile") else ""}></audio>
<div class="previews">{cards}</div><hr><p>Selected: <b>{html.escape(str(state.get("selectedPreview") or "none"))}</b></p>
<form method="post" action="/approve"><button {"" if state.get("selectedPreview") else "disabled"}>Approve selected voice</button></form>
<p class="muted">Approval only unlocks narration regeneration; it does not render video.</p></section></div></main>
<script>const contract={contract_json};const caps=contract.providers.find(p=>p.provider_id===contract.state.voiceProvider).capabilities;
const mode=document.querySelector('#mode');function visibility(){{const design=mode.value==='voice_design';document.querySelector('#gender-wrap').classList.toggle('hidden',!(design&&caps.gender));document.querySelector('#age-wrap').classList.toggle('hidden',!(design&&caps.age));document.querySelector('#pitch-wrap').classList.toggle('hidden',!(design&&caps.pitch));document.querySelector('#reference-wrap').classList.toggle('hidden',!(mode.value==='voice_clone'&&caps.reference_audio));}}mode.addEventListener('change',visibility);visibility();
const speed=document.querySelector('#speed');speed.addEventListener('input',()=>document.querySelector('#speed-label').textContent=Number(speed.value).toFixed(2)+'x');
document.querySelector('#provider').addEventListener('change',()=>{{location.href='/?provider='+encodeURIComponent(document.querySelector('#provider').value)}});
document.querySelector('#profile').addEventListener('change',e=>{{const p=contract.profiles.find(x=>x.profile_id===e.target.value);if(!p)return;if(p.provider!==document.querySelector('#provider').value){{location.href='/?provider='+encodeURIComponent(p.provider);return}}mode.value=p.mode;document.querySelector(`input[name="gender"][value="${{p.design?.gender||'male'}}"]`).checked=true;document.querySelector('#pitch').value=p.design?.pitch||'moderate';speed.value=p.speed;document.querySelector('#speed-label').textContent=Number(p.speed).toFixed(2)+'x';document.querySelector('#voice-id').value=p.voice_id||'';visibility();}});
</script></body></html>'''


def serve_voice_control(control: VoiceControlService, port: int = 8822, open_browser: bool = True) -> None:
    class Handler(BaseHTTPRequestHandler):
        def redirect(self, message: str) -> None:
            self.send_response(303)
            self.send_header("Location", "/?" + urlencode({"message": message}))
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/audio":
                candidate = (control.preview_root / Path(query.get("name", [""])[0]).name).resolve()
                if not candidate.is_relative_to(control.preview_root.resolve()) or not candidate.is_file():
                    self.send_error(404)
                    return
                body = candidate.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            provider = query.get("provider", [None])[0]
            if provider:
                try:
                    control.update_state(provider=provider, mode="auto")
                except Exception as exc:
                    query["message"] = [str(exc)]
            page = voice_control_page(control, query.get("message", [""])[0]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def _multipart(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            envelope = f"Content-Type: {self.headers['Content-Type']}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
            message = BytesParser(policy=default).parsebytes(envelope)
            return {part.get_param("name", header="content-disposition"): part for part in message.iter_parts()}

        def do_POST(self) -> None:  # noqa: N802
            try:
                if self.path == "/generate":
                    fields = self._multipart()
                    values = {key: _form_text(part) for key, part in fields.items() if key != "reference_audio"}
                    reference = fields.get("reference_audio")
                    if reference is not None and reference.get_filename():
                        suffix = Path(reference.get_filename()).suffix or ".wav"
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                            handle.write(reference.get_payload(decode=True))
                            temp_path = Path(handle.name)
                        try:
                            control.choose_reference_audio(temp_path)
                        finally:
                            temp_path.unlink(missing_ok=True)
                    control.update_state(
                        provider=values["provider"], mode=values["mode"], gender=values.get("gender", "male"),
                        age=values.get("age", "young adult"), pitch=values.get("pitch", "moderate"),
                        speed=float(values["speed"]), voice_id=values.get("voice_id") or None,
                        preview_text=values["preview_text"],
                    )
                    result = control.generate_preview(output_path=control.preview_root / "custom_preview.wav")
                    self.redirect(f"Preview ready: {result.duration:.3f}s")
                    return
                length = int(self.headers.get("Content-Length", "0"))
                values = {key: items[0] for key, items in parse_qs(self.rfile.read(length).decode()).items()}
                if self.path == "/comparisons":
                    control.generate_comparison_previews()
                    self.redirect("Four comparison previews are ready.")
                elif self.path == "/select":
                    control.select_preview(values["preview"])
                    self.redirect(f"Selected {values['preview']}; project config updated, not yet approved.")
                elif self.path == "/approve":
                    control.approve_voice()
                    self.redirect("Voice approved. Narration regeneration is now unlocked.")
                else:
                    self.send_error(404)
            except Exception as exc:  # pragma: no cover - browser error path
                self.redirect(f"Error: {exc}")

        def log_message(self, _format: str, *_args: object) -> None:
            return

    url = f"http://127.0.0.1:{port}/"
    print(f"Voice control UI: {url}")
    if open_browser:
        webbrowser.open(url)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
