# Agent-first video workflow

The desktop UI is optional. The production entry point is the local CLI:

```powershell
python app.py build-video --zip .\source.zip --script .\script.txt --project my-project [--config .\project_config.json]
```

## Input

- `source.zip`: Google Flow clips named `Scene_1_*.mp4`, `Scene_2_*.mp4`, and so on.
- `script.txt`: `SCENE N` / `Narration:` blocks. The supplied narration is stored verbatim.
- Optional `project_config.json`: voice settings and per-scene trim, speed, crop, transition, hold-frame, or source-audio settings.

## Pipeline

The command creates or resumes `projects/<project>/`, discovers and numerically sorts scenes, probes every source with ffprobe, keeps duplicate versions, maps the script, approves the first readable source version by default, generates OmniVoice narration and subtitle timing, applies scene settings, renders a 720x1280 preview, then renders and masters a 1080x1920 final MP4 with FFmpeg. Both outputs are validated from real ffprobe metadata.

Voice is an explicit resumable stage. It logs per-scene progress under
`metadata/logs/voice-progress.json` and caches each scene WAV. A rerun reuses matching
cache entries instead of regenerating earlier scenes. The default CPU-safe OmniVoice setting
is 4 steps; use `--voice-num-step 8` or `16` only when the machine can sustain it. CPU runs
emit a warning but are allowed to continue.

## Output

- `projects/<project>/render/preview/preview.mp4`
- `projects/<project>/render/final/final.mp4`
- `projects/<project>/build_report.json`

The report contains stage status, warnings, source probes, voice settings, output paths, timing, and errors. A failed or mismatched scene stops final rendering and is recorded in the report; it is never silently dropped.

## Common edit commands

Use the existing CLI commands for incremental changes, for example:

```powershell
python app.py set-scene-audio my-project --scene scene_07 --version 1 --mode mute
python app.py set-scene-video-speed my-project --scene scene_07 --version 1 --speed 1.15
python app.py render-preview my-project
python app.py approve-preview my-project
python app.py render-video my-project
```

Voice preview is available with `python app.py voice-preview <project>`. OmniVoice is the only active provider; VoiceStudio is not installed, started, or called.

For pipeline-only diagnostics, `--use-existing-voice` reuses complete per-scene WAVs and
`--skip-voice` creates silent WAVs. Both flags are test-only; `--skip-voice` is reported as
`PARTIAL_PASS` and the normal command never falls back to mock audio.

## Error handling

Unreadable clips, missing scene numbers, script/video mismatches, invalid trim ranges, unsupported voice settings, failed synthesis, and output metadata mismatches are reported in `build_report.json`. The command exits non-zero when a final render is unsafe.

## Remote-ready boundary

The build service uses relative project paths and environment-resolved tools (`node`, `ffmpeg`, `ffprobe`). Heavy OmniVoice, Remotion, and FFmpeg operations are isolated behind services so an agent, remote VM, CI runner, or stronger workstation can invoke the same command without the desktop app or a Windows EXE.
