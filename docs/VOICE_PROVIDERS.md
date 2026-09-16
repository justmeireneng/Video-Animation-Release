# Voice providers

Production voice engine: **OmniVoice**.

## Active architecture

```text
VoiceProvider
└── OmniVoiceProvider  [ACTIVE]
```

`VoiceProvider` remains the provider-neutral contract for a future extension, but the production registry, CLI, and Voice Control panel activate only `omnivoice`.

The current OmniVoice adapter uses the existing Vietnamese Edge TTS runtime. It does not download OmniVoice model weights during startup or preview generation.

## Current OmniVoice capabilities

| Capability | Status |
| --- | --- |
| Auto mode | Available |
| Voice Design | Available, using Vietnamese male/female presets |
| Voice Clone | Not implemented; hidden |
| Gender | Male / Female |
| Age | Not implemented; hidden |
| Pitch | Low / Moderate / High |
| Speed | 0.85x–1.20x |
| Reference audio | Not implemented; hidden |
| Preview before video render | Available |

The speed control uses Edge TTS rate independently from pitch. The presets are 0.95 Slow, 1.00 Normal, 1.08 Natural+, 1.10 Default, 1.12 Fast, and 1.15 Fast+.

The active default is:

```json
{
  "voice": {
    "provider": "omnivoice",
    "mode": "voice_design",
    "language": "vi",
    "design": {
      "gender": "male",
      "pitch": "moderate"
    },
    "speed": 1.10
  }
}
```

`age` is deliberately absent from the active configuration because the current adapter cannot apply it. This keeps the configuration, cache key, and UI truthful to the runtime.

## Preview and cache

Voice Control and `python app.py voice-preview <project>` create WAV previews only; neither command renders video. The voice cache reuses an existing audio file only when text, mode, gender, age, pitch, speed, and reference-audio content are identical.

## VoiceStudio status

VoiceStudio is **disabled and outside the current scope** because its local resource footprint is too heavy for the target hardware.

- No runtime dependency, model download, backend startup, health check, API call, or production bundle path is active.
- The prior remote adapter source is retained as an inactive future-experiment artifact only. It is not registered, imported by startup, exposed in the CLI/UI, or exercised by regression tests.
- Re-enabling it requires an explicit future product decision and a new validation pass.

## Preserved video workflow

Disabling VoiceStudio does not alter Flow ZIP import, dynamic scenes, scripts, source versioning, source audio controls, trim, playback rate, crop, transitions, Vietnamese subtitles, Remotion, FFmpeg, or preview/final render workflows.
