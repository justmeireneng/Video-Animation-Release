# Google Colab quick start

The repository includes [`colab/AI_Video_Studio.ipynb`](../colab/AI_Video_Studio.ipynb). It is
an execution wrapper around the canonical `python app.py build-video` pipeline; it does not
maintain a second renderer.

## Quick start

1. Open the notebook in Colab.
2. Choose **Runtime → Change runtime type → GPU** when a GPU is available.
3. Create `MyDrive/AI_Video_Studio/input/` and put `source.zip` and `script.txt` there.
4. Edit `PROJECT_NAME` in the first configuration cell if needed.
5. Select **Runtime → Run all** and authorize Google Drive.
6. Wait for the pipeline to finish.
7. Open `MyDrive/AI_Video_Studio/output/<project>/final.mp4`.

The notebook creates these persistent folders automatically:

```text
MyDrive/AI_Video_Studio/
├── input/
├── output/<project>/
├── models/          # Hugging Face/OmniVoice cache
├── cache/           # reserved persistent cache area
├── projects/<project>/  # resumable project state and per-scene voice cache
└── logs/<project>/
```

## What Run all does

The notebook mounts Drive, validates both inputs, clones the pinned repository checkout,
installs `requirements.txt` and first attempts the locked Remotion dependencies, checks ffmpeg/ffprobe,
detects the real PyTorch CUDA device, prepares the persistent OmniVoice model cache, copies
work into `/content/ai-video-work/`, and runs:

```bash
python app.py build-video \
  --zip /content/ai-video-work/input/source.zip \
  --script /content/ai-video-work/input/script.txt \
  --project <project>
```

The core command remains responsible for import, dynamic scene mapping, ffprobe checks,
OmniVoice, subtitles, source audio, Remotion, FFmpeg, and final validation. The final MP4 is
copied back only after a `FULL_PASS` report. A failed build still persists its project state,
voice cache, logs, and `build_report.json` so the next Run all can resume.

## Voice and cache behavior

OmniVoice is the only active provider. The notebook exports `OMNIVOICE_DEVICE=cuda` only when
both `nvidia-smi` and `torch.cuda.is_available()` confirm a usable GPU; otherwise it reports a
CPU fallback warning. The current runner supports fp16 and lazy model loading. It does not
claim bf16, int8, quantization, batching, or chunked inference support.

Each scene's voice cache is keyed by the existing provider/config/text hash. Use
`FORCE_REGENERATE_VOICE = True` only when intentionally invalidating local voice artifacts.
`FORCE_REBUILD = True` clears render artifacts while retaining the voice cache.

Set `TEST_MODE = True` only for a deliberate diagnostic run. The flags
`TEST_USE_EXISTING_VOICE` and `TEST_SKIP_VOICE` are disabled by default and require
`TEST_MODE=True`; the latter creates silent WAVs and produces `PARTIAL_PASS`, never a
production `FULL_PASS`. TEST_MODE does not silently reduce the scene count.

## Outputs and reports

- `output/<project>/final.mp4`
- `output/<project>/build_report.json`
- `output/<project>/colab_run_report.json`
- `logs/<project>/build-console.log`

Reports include import/mapping status, voice device and cache hits, stage timings, output
metadata, warnings, and errors. If Colab has no GPU, the build remains valid but voice
generation may be slow. No Flow/Veo API, paid TTS, VoiceStudio, EXE, or private token is
required. If a Colab/Linux pnpm version rejects the Windows-generated lockfile metadata,
the notebook prints the exact pnpm error and retries without frozen-lockfile only inside the
ephemeral `/content/ai-video-work` checkout; the GitHub repository is never modified.

## Open in Colab

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/justmeireneng/Video-Animation-Release/blob/main/colab/AI_Video_Studio.ipynb)

The repository has not been executed in an actual Colab runtime from this local session. The
notebook is implementation-ready; the first real run should be treated as the environment
validation/benchmark run and will write its measured setup, model, voice, preview, final, and
total timings to `colab_run_report.json`.
