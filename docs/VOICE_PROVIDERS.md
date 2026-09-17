# Voice providers

Production voice engine: **OmniVoice**.

## Active architecture

```text
VoiceProvider
└── OmniVoiceProvider  [ACTIVE]
```

`VoiceProvider` remains the provider-neutral contract for a future extension, but the production registry, CLI, and Voice Control panel activate only `omnivoice`.

The current adapter runs the real `k2-fsa/OmniVoice` model in an isolated local
Python process. The model is loaded only when generating audio; app startup and
health checks never load weights or download files. Inference is forced offline
and no Edge TTS/cloud fallback is used.

## Current OmniVoice capabilities

| Capability | Status |
| --- | --- |
| Auto mode | Available |
| Voice Design | Available through native `instruct` attributes |
| Voice Clone | Not implemented; hidden |
| Gender | Male / Female |
| Age | Young adult / middle-aged / older adult |
| Pitch | Low / Moderate / High |
| Speed | 0.85x–1.20x |
| Reference audio | Not implemented; hidden |
| Preview before video render | Available |

The speed control is passed to OmniVoice's native `speed` input and does not alter the pitch setting. The presets are 0.95 Slow, 1.00 Normal, 1.08 Natural+, 1.10 Default, 1.12 Fast, and 1.15 Fast+.

The active default is:

```json
{
  "voice": {
    "provider": "omnivoice",
    "mode": "voice_design",
    "language": "vi",
    "design": {
      "gender": "male",
      "age": "young adult",
      "pitch": "moderate"
    },
    "speed": 1.10
  }
}
```

On the current CPU-only target, a short preview uses an isolated worker. With
less than 3 GB of physical RAM free, the app enters a measured low-memory mode
and relies on the Windows pagefile; this is slower but remains functional. It
blocks only when total remaining RAM/pagefile commit capacity is too low to
start the worker safely.

## Preview and cache

Voice Control and `python app.py voice-preview <project>` create WAV previews only; neither command renders video. The voice cache reuses an existing audio file only when text, mode, gender, age, pitch, speed, and reference-audio content are identical.

The desktop preview endpoint uses 4 diffusion steps to stay responsive on the
8 GB target machine. Full scene narration retains the 16-step provider default;
the two qualities use separate cache entries.

## VoiceStudio status

VoiceStudio is **disabled and outside the current scope** because its local resource footprint is too heavy for the target hardware.

- No runtime dependency, model download, backend startup, health check, API call, or production bundle path is active.
- The prior remote adapter source is retained as an inactive future-experiment artifact only. It is not registered, imported by startup, exposed in the CLI/UI, or exercised by regression tests.
- Re-enabling it requires an explicit future product decision and a new validation pass.

## Preserved video workflow

Disabling VoiceStudio does not alter Flow ZIP import, dynamic scenes, scripts, source versioning, source audio controls, trim, playback rate, crop, transitions, Vietnamese subtitles, Remotion, FFmpeg, or preview/final render workflows.
