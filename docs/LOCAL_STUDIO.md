# Local AI Video Studio workflow

## Start the local application

From the repository root:

```powershell
.\.venv\Scripts\python.exe app.py serve-studio --port 8766
```

Open `http://127.0.0.1:8766/` in a local browser. The server binds to
`127.0.0.1` by default. It serves the UI and a loopback-only API; it does not
send projects or source media to a cloud service.

## Creator flow

1. Create a project. A new project has its own `project.json`, `remotion.json`
   and media folders below `projects/<project-id>/`.
2. Import a Google Flow ZIP through the UI, or import a ZIP/folder by CLI.
   ZIP entries are checked for path traversal, encryption, entry count and
   uncompressed size before import. Filenames matching
   `Scene[_ -]?(\d+)` are sorted numerically; gaps remain visible as missing
   scene slots rather than being renumbered. If all Flow filenames are generic,
   videos map to Scene 1, 2, ... in ZIP entry order. The Import screen shows
   the source filename beside each proposed scene so you can check that order
   before approving narration. An archive with no supported video reports an
   error instead of silently continuing. Re-uploading an already successful
   identical ZIP reuses its import rather than creating extra versions. The
   Import screen can play each original clip locally (byte-range streaming),
   without generating a preview render.
3. Inspect and approve the immutable `flow_vN` source version for each scene.
   An original source file is never overwritten.
4. Paste or import the per-scene script, then approve its mapping. The text is
   stored as supplied; it is not rewritten by an AI service.
5. Configure and preview the voice, approve it, prepare narration/subtitles,
   render a preview, review it, and approve that preview before final render.
   The render preflight rejects a new project with an unapproved video, script,
   voice or missing narration audio.
6. Make source trim, crop, source-audio, 0.50–2.00x video-speed, hold-last-
   frame and transition adjustments non-destructively, then render a new
   preview before final export.

## Useful CLI commands

```powershell
.\.venv\Scripts\python.exe app.py new-project "My documentary"
.\.venv\Scripts\python.exe app.py import-flow-zip my-documentary C:\path\flow.zip
.\.venv\Scripts\python.exe app.py import-script my-documentary C:\path\script.txt
.\.venv\Scripts\python.exe app.py approve-script-mapping my-documentary
.\.venv\Scripts\python.exe app.py set-scene-video-speed my-documentary --scene scene_01 --version 1 --speed 1.25
.\.venv\Scripts\python.exe app.py set-scene-hold-last-frame my-documentary --scene scene_01 --version 1 --enabled true
```

## Voice status

The only active provider identity is `omnivoice`; VoiceStudio is not installed,
loaded, health-checked, called, or bundled. Voice preview uses the real local
OmniVoice model in `.venv-omnivoice` with offline model loading. It does not use
Edge TTS or another cloud fallback. The model's CC-BY-NC terms fit this personal,
non-commercial phase; reassess before any commercial distribution. See
`docs/VOICE_PROVIDERS.md` and `docs/DEPENDENCY_LICENSES.md`.

## Packaging status

This is a local developer application, not yet a shippable Windows installer.
Installer work remains gated on an approved OmniVoice model distribution plan,
the applicable Remotion licence, and a documented FFmpeg binary/compliance
package. No automatic model or VoiceStudio download is performed.
