# Project Context

## Current direction: ZIP-first source video

Creators generate scene MP4 files manually in Google Flow Ultra, download a ZIP/folder, then
import it locally. Filenames containing `Scene_<number>` are numerically mapped to project scene
indices, probed, versioned without overwrite, reviewed, and approved. Remotion composes approved
Flow clips first while preserving approved-image animation fallback. OmniVoice remains the master
narration; source ambience is controlled per scene. Flow/Veo API calls and Flow browser automation
are explicitly outside the current phase.

## Current direction: cartoon-first Remotion pipeline

The primary composition target is now a modern 2D cartoon educational explainer for vertical
TikTok, Shorts, and Reels. Scene images remain visual-first and human-approved. Remotion adds
deterministic semantic motion, the fixed `creator_01` mascot, captions, transitions, narration,
and SFX. It never generates the scene artwork.

The repository deliberately keeps both runtimes:

- Python: story, storyboard, image-provider adapters, OmniVoice/EdgeTTS, review, SFX, orchestration.
- Node/Remotion: animation, layout, mascot, subtitle presentation, timeline, MP4 render.

The existing FFmpeg and cinematic renderer code remains intact for mastering and fallback.
The sample's current scene PNG files are legacy photorealistic assets; they may be used for
technical integration testing but do not satisfy the final cartoon-art direction until a human
approves replacement illustrations.

Review flow: generate image -> contact-sheet review -> approve -> build/validate Remotion JSON
-> Studio review -> test render -> video review -> final render/master.

## Remotion audit (2026-09-11)

- Stable version audited and pinned: `4.0.523`.
- Runtime requirement: Node.js `>=16`; Node 24 is verified locally.
- Package manager: pnpm is used locally; npm, yarn, and Bun are also supported by Studio docs.
- Studio: `remotion studio`; CLI render: `remotion render`; Node rendering APIs include
  `bundle()`, `selectComposition()`, and `renderMedia()`.
- Dynamic data: input props plus `calculateMetadata()` drive JSON-loaded composition metadata.
- Media: `<Img>`/`staticFile()` for images and `<Audio>` from `@remotion/media` for audio.
- Captions: Remotion provides `@remotion/captions`; this project renders its already-timed phrase
  JSON directly to preserve the current subtitle pipeline.
- Animation: `interpolate()`, `spring()`, and easing utilities; transition APIs are available in
  `@remotion/transitions`. This module uses lightweight deterministic transitions for weaker CPUs.
- Output: CLI defaults to H.264 and supports MP4 audio encoding. Local rendering uses a browser
  runtime and Remotion's packaged compositor; system FFmpeg remains required for the legacy final
  mastering pipeline.

### Remotion license

Remotion is source-available under its own two-tier Remotion License, **not MIT**. The free license
covers individuals, non-profit/not-for-profit organizations, evaluation, and for-profit organizations
with up to three employees; eligible users may create commercial videos. Other for-profit entities
must obtain a Company License. Selling or sublicensing a modified derivative of Remotion itself is
not permitted under the free terms. Re-check the license before organizational/commercial deployment:
https://github.com/remotion-dev/remotion/blob/main/LICENSE.md

## Project Vision
- **T?n d? ?n**: AI Video Animation Generator (Video Animation Studio)
- **M?c ti?u**: X?y d?ng h? th?ng t? ??ng h?a s?n xu?t video gi?i th?ch c?ng ngh? (AI Explainer) ??nh d?ng d?c 9:16 t?i ?u cho TikTok, YouTube Shorts v? Meta Reels.
- **Input**: M?t ch? ?? duy nh?t (Topic).
- **Output**: M?t video ho?n ch?nh bao g?m:
  - K?ch b?n & Hook gi? ch?n ng??i xem (Script).
  - C?u tr?c ph?n c?nh chi ti?t (Storyboard).
  - C?c khung h?nh ?i?n ?nh s?c n?t (Visual Scenes).
  - Gi?ng ??c thuy?t minh t? nhi?n (Narration).
  - Ph? ?? ??ng canh chu?n v?ng an to?n (Dynamic Subtitles).
  - ?m thanh chi ti?t ??ng b? h?nh ??ng (Sound Design / SFX).
  - Video th?nh ph?m ???c ph?i gh?p ho?n thi?n (Final Video).

---

## Current Philosophy
D? ?n ?? th?c hi?n b??c chuy?n ??i chi?n l??c c?t l?i:

- **FROM**: Whiteboard Animation Renderer (V? tay b?ng tr?ng ho?t h?nh gi? l?p)
- **TO**: Visual-First AI Video Production Pipeline (Quy tr?nh s?n xu?t video ?i?n ?nh l?y h?nh ?nh l?m trung t?m)

### L? do chuy?n ??i:
H? th?ng Whiteboard Renderer b?c l? c?c h?n ch? k? thu?t v? th?m m? nghi?m tr?ng:
1. **Ch?t l??ng h?nh ?nh gi?i h?n**: Tranh v? tay vector ??n s?c kh? truy?n t?i c?c ? t??ng c?ng ngh? ph?c t?p hay chi?u s?u s?n ph?m.
2. **Chuy?n ??ng l?p l?i**: C?nh tay ??a qua l?i li?n t?c g?y c?m gi?c nh?m ch?n v? che khu?t th?ng tin ch?nh.
3. **Kh? t?o c?m gi?c ?i?n ?nh (Cinematic Storytelling)**: Thi?u v?ng ?nh s?ng studio, g?c m?y ?i?n ?nh v? chi?u s?u kh?ng gian l?m vi?c th?c t?.
4. **Kh? m? r?ng**: Kh?ng t?n d?ng ???c b??c ti?n v??t b?c c?a c?c m? h?nh khu?ch t?n h?nh ?nh/video hi?n ??i.

### H??ng ?i m?i:
X?y d?ng pipeline nh? m?t h?ng s?n xu?t phim t?i li?u c?ng ngh? th?c th? (t??ng t? s?n ph?m truy?n th?ng c?a Google Flow v? Dola AI), n?i AI t?o ra t?ng c?nh quay v?i b? c?c ch?t ch?, ?nh s?ng ch?n th?c v? chuy?n ??ng m?y quay tinh t?.

---

## Current Pipeline (v0.1)

```text
Topic
  ?
Story Agent (Creative Director)
  ?
Script (Narration ph?n ?o?n)
  ?
Storyboard (C?u tr?c ph?n c?nh & Visual Intent)
  ?
Visual Bible (M?u s?c, ?nh s?ng, Camera, Nh?n v?t, B?i c?nh)
  ?
Scene JSON & Prompt Conditioning
  ?
Image Generation (8 Master Keyframes 9:16)
  ?
Human Review (Storyboard Contact Sheet 8 Shots)
  ?
Voice Generation (OmniVoice / EdgeTTS)
  ?
Subtitle Engine (TikTok Safe Area Y ? 1450)
  ?
Sound Design (SFX h?nh ??ng + Dynamic Ducked BGM)
  ?
FFmpeg Composition (Muxing, H.264 FastStart < 20MB)
  ?
Final Video
```

---

## Source-video pipeline (v0.3)

```text
Google Flow Ultra manual generation
  ?
Downloaded ZIP/folder with Scene_<number> MP4 files
  ?
Map, ffprobe, immutable versioning, source review
  ?
Approved video or approved-image fallback
  ?
Compositor & Audio Conform
  ?
Final Render
```

---

## Design Principles

1. **Semantic First (Ng? ngh?a l?m tr?ng t?m)**:
   - M?i y?u t? tr?n h?nh ?nh ph?i tr?c ti?p ph?c v? v? l?m r? l?i thuy?t minh (Narration). Tuy?t ??i kh?ng sinh h?nh ?nh ng?u nhi?n ch? ?? "l?p ch? tr?ng".

2. **Consistency First (T?nh nh?t qu?n s?n xu?t)**:
   - T?t c? c?c c?nh quay trong video ph?i mang l?i c?m gi?c c?a c?ng m?t b? phim, c?ng m?t nh?n v?t (`creator_01`), c?ng m?t kh?ng gian l?m vi?c (creative tech studio) v? c?ng m?t b?ng m?u ?i?n ?nh (than ch? - h? ph?ch - cyan).

3. **Human Review (Con ng??i gi? quy?n quy?t ??nh)**:
   - AI ??ng vai tr? ?? xu?t k?ch b?n, ? ?? th? gi?c v? t?o nguy?n m?u. Con ng??i gi? vai tr? ph? duy?t (Review Gates) th?ng qua b?ng Storyboard Contact Sheet tr??c khi xu?t b?n.

4. **Provider Abstraction (L?p tr?u t??ng h?a m? h?nh)**:
   - To?n b? pipeline ???c module h?a qua c?c Interface tr?u t??ng (`ImageProvider`, `VideoProvider`, `VoiceProvider`, `CompositorProvider`). H? th?ng kh?ng b? kh?a v?o b?t k? m?t nh? cung c?p AI n?o.
