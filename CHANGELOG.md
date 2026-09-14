# Changelog

All notable changes to the **Video Animation** project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- ZIP-first Google Flow manual import for ZIP/folders, robust scene parsing and numeric sort,
  ffprobe validation, immutable `flow_vN.mp4` versions, duplicate/missing/invalid reports, and
  explicit project workflow state.
- Per-scene source review UI and CLI controls for approve/reject/rollback, trim, cover/contain
  focal crop, source-audio mute/background/full, volume/ducking/fades, transition, and subtitle
  vertical offset.
- Fast 540x960 preview rendering plus Remotion-to-FFmpeg final mastering at 1080x1920/30fps.
- Bundled Be Vietnam Pro font files for deterministic Vietnamese subtitle glyph coverage.
- JSON-driven Remotion 4.0.523 composition runtime with four vertical layouts, deterministic
  animation presets, focal-point motion, mascot fallback, phrase subtitles, narration, SFX,
  Studio preview, CLI rendering, Python wrappers, and loader tests.

### Changed
- Approved manual Flow video now has visual priority over imported/generated video and approved
  image animation fallback; OmniVoice narration remains the master timeline.
- Primary composition direction is now 2D cartoon educational animation while the existing
  Python, OmniVoice, FFmpeg, review, and cinematic fallback modules remain intact.

## [0.1.0] - 2026-09-09

### Added
- **Visual-First AI Explainer Architecture**: Transitioned from whiteboard line-drawing to photorealistic cinematic tech documentary pipeline.
- **Global Visual Bible**: Defined strict production rules for Genre, Color Bible (Charcoal, Amber, Cyan), Lighting (Soft Directional Daylight), Camera Language (35mm/50mm/85mm), Character (`creator_01`), and Studio Environment.
- **Reference System**: Added 3 master reference anchors (`character_reference`, `environment_reference`, `style_reference`) ensuring character and studio consistency across all scenes.
- **Pluggable Providers**: Abstracted `ImageProvider`, `VideoProvider`, `VoiceProvider`, and `CompositorProvider` to eliminate vendor lock-in.
- **Cinematic 2.5D Motion Engine**: Implemented CPU-optimized 2.5D Depth Saliency Parallax, Anamorphic Volumetric Light Sweep, and 3D Atmospheric Particles.
- **Voice Narration**: Integrated `OmniVoice` with zero-shot voice design, along with high-reliability `EdgeTTS` fallback (`vi-VN-NamMinhNeural`).
- **Dynamic TikTok Subtitles**: ASS generator with TikTok Safe Area positioning ($Y \approx 1450\text{px}$), high-contrast outline, and amber key-phrase highlighting.
- **Sound Design**: Procedural action-mapped SFX (typing, card snaps, ticks, whooshes) and dynamic ducked ambient music (-14dB).
- **FFmpeg Compositor**: Full automated muxing, EBU R128 loudness normalization, and H.264 FastStart compression under 20MB.
- **Sample Project**: Included complete verified 8-scene production project `Astra_AI_Explainer` (70.78s, 14.3 MB).
- **CLI Utilities**: Added `app.py` with `status` and `export-project` commands for easy backups and packaging.
