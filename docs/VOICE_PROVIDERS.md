# Voice providers

Audit snapshot: 2026-09-16. This document describes the integration boundary used by this project; it is not legal advice.

## Architecture

`omnivoice` remains `default_voice_provider`. It is the local default and continues to use the existing Edge TTS-backed adapter. `voicestudio_remote` is an opt-in HTTP/HTTPS client only:

```text
Local AI Video Studio -- HTTPS / private overlay --> Remote VoiceStudio backend
                                                   --> remote TTS engine/model
                                                   --> WAV response --> local audio cache
```

The local project never installs, starts, launches, or downloads VoiceStudio models. It only sends text/configuration to an explicitly configured remote endpoint, receives audio, and caches that output under the project.

`VoiceProvider` normalizes synthesis to `audio_file`, `provider`, `voice_id`, `language`, `duration`, `sample_rate`, and optional `timing`. Remote request metrics are reported separately: time to first response, download time, total request time, returned synthesis time when the server exposes it, audio duration, and output size.

The cache key includes provider, **remote base URL**, engine, voice, mode, gender, age, pitch, speed, text, and reference-audio hash. It deliberately excludes secrets, video, crop, transition, and subtitle-position changes. `.voice-cache/`, `.voice-preview/`, and Voice Control state are generated and ignored by Git.

## OmniVoice

- Provider ID: `omnivoice` (default).
- Current behavior is retained: Vietnamese Edge TTS fallback, preset male/female voices, native rate and pitch controls.
- No VoiceStudio source, model, runtime, virtual environment, Docker image, or local backend is required.

## VoiceStudio Remote

- Provider ID: `voicestudio_remote`.
- Remote API: `GET /health`, `GET /v1/audio/voices`, and OpenAI-compatible `POST /v1/audio/speech`.
- Configuration:

```json
{
  "voice": {
    "provider": "voicestudio_remote",
    "base_url": "https://voice.example.net",
    "timeout_seconds": 180,
    "engine": "tts-1",
    "voice_id": "remote-profile-id",
    "language": "vi",
    "speed": 1.12
  }
}
```

- Set the secret outside project files: `VOICESTUDIO_API_KEY`. The adapter sends it only as `Authorization: Bearer <key>` and never writes it to project JSON, cache metadata, logs, or Git.
- Set `VOICESTUDIO_BASE_URL` and optional `VOICESTUDIO_TIMEOUT_SECONDS` when a project does not specify the endpoint.
- `localhost`, `.localhost`, `127.0.0.1`, and `::1` are rejected so the integration cannot accidentally use a local VoiceStudio service.
- Voice profiles and engines are discovered from the remote runtime; the app does not copy an engine list from the README.
- Voice cloning uses a saved **remote** profile ID. Uploading a local reference file to this API is not supported.
- Voice design is engine-dependent. The remote API accepts its documented free-form `description`, but this app hides generic gender/age/pitch controls until a remote engine explicitly reports compatible capabilities.

### Connection security

Use HTTPS or an encrypted private overlay such as Tailscale. Plain HTTP is acceptable only on a trusted private network because Bearer credentials are otherwise visible in transit. On the remote machine, set `OMNIVOICE_API_KEY`; upstream documents that remote direct clients use the `Authorization: Bearer` header. Do not expose port 3900 unauthenticated or put the key in a URL.

The Voice Control panel exposes a Remote Server URL, transient API Key field, and **Test Connection** action. The key is sent only for that request/preview and is not persisted. For repeated CLI use, use `VOICESTUDIO_API_KEY` instead of command-line flags or checked-in configuration.

## Commands

```powershell
python app.py voice-providers
python app.py voice-preview Atlantic_Ocean_Explainer
python app.py voice-preview Atlantic_Ocean_Explainer --provider voicestudio_remote --remote-base-url https://voice.example.net --engine tts-1
python app.py voice-control Atlantic_Ocean_Explainer
```

`voice-control` generates previews only; it never renders video. Remote failure is explicit and does not silently switch to OmniVoice. The project can always be switched back to `omnivoice`.

## Disposable remote test choices

1. A temporary GPU VM or RunPod instance behind Tailscale Serve is the most direct disposable test: run the pinned VoiceStudio backend remotely, select one engine, test previews, then stop the instance.
2. A cloud VM or private remote Docker host works the same way; keep port 3900 private behind TLS/reverse proxy or an encrypted overlay.
3. Google Colab or GitHub Codespaces can be used for experiments only after you provide a private authenticated endpoint. Do not expose an unauthenticated notebook tunnel to the public internet.

The remote deployment, engine weights, compute, and model-license obligations belong to that remote environment. This repository remains a thin client.

## Licensing

- VoiceStudio application code is AGPL-3.0-only. Running it as a remote service may carry AGPL source-offer obligations; obtain legal review before proprietary distribution or network operation.
- VoiceStudio engines and downloaded model weights retain their own terms. The VoiceStudio application license does not relicense them.
- OmniVoice upstream code is Apache-2.0, while its published weights have separate CC-BY-NC and tokenizer terms. Review all applicable terms before commercial use.

Primary API audit sources: [VoiceStudio API authentication](https://github.com/debpalash/VoiceStudio/blob/main/docs/api-auth.md), [remote GPU guide](https://github.com/debpalash/VoiceStudio/blob/main/docs/remote-gpu.md), and [OpenAI-compatible router](https://github.com/debpalash/VoiceStudio/blob/main/backend/api/routers/openai_compat.py).
