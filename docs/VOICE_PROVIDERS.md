# Voice providers

Audit snapshot: 2026-09-15. This document describes the integration boundary used by this project; it is not legal advice.

## Architecture

`omnivoice` remains `default_voice_provider`. Project-specific selection lives in `projects/<name>/narration.json`:

```json
{
  "voice": {
    "provider": "omnivoice",
    "mode": "auto",
    "voice_id": "vi-VN-NamMinhNeural",
    "language": "vi-VN",
    "speed": 0.92,
    "engine": null,
    "design": {"gender": "male", "age": null, "pitch": null}
  }
}
```

`VoiceProvider` normalizes synthesis to `audio_file`, `provider`, `voice_id`, `language`, `duration`, `sample_rate`, and optional `timing`. `ProviderRegistry` imports only the selected provider. A missing optional provider is reported and falls back explicitly to OmniVoice; startup never downloads models or starts an external service.

The cache key contains provider, runtime engine/model, voice ID, mode, gender, age, pitch, speed, text, and reference-audio SHA-256. Video, crop, transition, and subtitle-position changes are deliberately excluded. `.voice-cache/` and `.voice-preview/` are generated and ignored by Git.

Commands:

```powershell
python app.py voice-providers
python app.py voice-preview Atlantic_Ocean_Explainer
python app.py voice-preview Atlantic_Ocean_Explainer --provider voicestudio --engine tts-1
```

## OmniVoice

- Upstream: <https://github.com/k2-fsa/OmniVoice>
- This project's existing adapter is unchanged: it delegates synthesis to the existing EdgeTTS fallback when local OmniVoice weights are not loaded.
- The adapter currently supports multilingual synthesis, explicit male/female voice IDs, speed, and pitch. It does **not** implement upstream OmniVoice cloning, voice design, age control, or direct reference audio, so these are reported as unsupported.
- Upstream OmniVoice supports 600+ languages, zero-shot cloning, and voice design, but those features are not claimed by this adapter until wired and tested.
- Upstream code is Apache-2.0. The official model card states that the pretrained weights are CC-BY-NC because of training-data constraints: <https://huggingface.co/k2-fsa/OmniVoice>. That non-commercial weight license is separate from the code license and must be reviewed before commercial/proprietary use.

## VoiceStudio

- Upstream: <https://github.com/debpalash/VoiceStudio>
- Integration method: optional, separately running local service via `GET /health`, `GET /v1/audio/voices`, and OpenAI-compatible `POST /v1/audio/speech`. No VoiceStudio source or models are vendored into this repository.
- Configuration: `VOICESTUDIO_BASE_URL` (default `http://127.0.0.1:3900`) and optional `VOICESTUDIO_API_KEY`. `OMNIVOICE_API_KEY` is also honored because that is the upstream remote-server setting.
- Runtime engine IDs and saved voice profiles are discovered from `GET /v1/audio/voices`; no README engine list is copied into code. `tts-1` selects VoiceStudio's active engine. Voice design is engine-dependent. Cloning through this adapter uses a voice profile previously created in VoiceStudio; the OpenAI-compatible speech endpoint does not accept a raw reference upload.
- VoiceStudio has native batch/dubbing flows. This project keeps its existing narration strategy and provides provider-neutral `queued`, `generating`, `complete`, and `failed` scene states instead of copying VoiceStudio's UI or queue implementation.

### Runtime audit

- The backend is FastAPI/Uvicorn and exposes REST, SSE/WebSocket features, an OpenAI-compatible audio API, and an MCP shim. The adapter uses only the stable REST audio boundary.
- Current source declares Python 3.11+ and a large ML stack including PyTorch/torchaudio/torchvision, Transformers, Accelerate, Whisper-related packages, FastAPI, and engine-specific optional extras. These remain outside core requirements.
- Desktop/source development uses Bun/Node for the React frontend and Rust/Cargo for Tauri. They are not required when this project talks to an already running backend.
- The desktop distribution manages its own Python environment and model downloads. First launch/default-engine setup can download weights; this project never triggers installation or model downloads automatically.
- Windows 10 21H2+/11 x64 is supported. NVIDIA acceleration is optional; upstream documents CPU operation and notes Windows AMD GPU runs CPU-only. Practical accelerated use starts around 4 GB VRAM, 8 GB+ is recommended for the default path, and heavier engines may need 12–16 GB. CPU synthesis can be slow.
- VoiceStudio caches one engine instance and evicts other TTS engines during generation; it also has idle unloading. This project does not call admin unload endpoints because the external service owns its memory lifecycle.

Primary audit sources: [README](https://github.com/debpalash/VoiceStudio/blob/main/README.md), [Windows install guide](https://github.com/debpalash/VoiceStudio/blob/main/docs/install/windows.md), [Python project metadata](https://github.com/debpalash/VoiceStudio/blob/main/pyproject.toml), [API authentication](https://github.com/debpalash/VoiceStudio/blob/main/docs/api-auth.md), and [OpenAI-compatible router](https://github.com/debpalash/VoiceStudio/blob/main/backend/api/routers/openai_compat.py).

### License and packaging implications

- VoiceStudio application code is **AGPL-3.0-only**, not MIT or Apache. Its notice says the scope includes the Tauri shell, React frontend, FastAPI backend, and scripts: <https://github.com/debpalash/VoiceStudio/blob/main/LICENSE-NOTICE.md>.
- Running an unmodified, user-installed VoiceStudio service beside this project is the intentionally narrow integration boundary. If a product distributes, embeds, modifies, or operates VoiceStudio as a network service, AGPL source-offer/corresponding-source obligations may apply. Obtain legal review before proprietary packaging; a commercial VoiceStudio license may be available upstream.
- VoiceStudio's bundled OmniVoice code has separate Apache-2.0 terms, while its default OmniVoice weights are CC-BY-NC and its tokenizer has additional upstream terms. Other engines/models retain their own licenses. A commercial application license does not automatically relicense third-party weights.

## Setup boundary

Install and run VoiceStudio using its official instructions, then verify:

```powershell
$env:VOICESTUDIO_BASE_URL = "http://127.0.0.1:3900"
python app.py voice-providers
```

When VoiceStudio is absent, the catalog shows it as not installed/running and the Atlantic project continues with `omnivoice`.
