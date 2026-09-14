# AI Model Registry

## v0.2 active production stack

| Stage | Active component | Responsibility |
|---|---|---|
| Story | Existing Gemini story provider | Script and scene intent |
| Image | Approved cartoon illustration provider | Static 2D scene artwork only |
| Voice | OmniVoice, EdgeTTS fallback | Narration audio |
| Animation/composition | Remotion 4.0.523 | Programmatic React animation, layouts, mascot, captions, timeline |
| Audio/final conform | Existing FFmpeg pipeline | Ducking, loudness, mux, compatibility transcode |
| Scene video source | Manual Google Flow ZIP/folder import | External creation; local map, probe, version and review |

Remotion is **not a generative video model**. It is a programmatic animation and composition
engine. It does not create or approve scene illustrations.

B?ng ph?n lo?i chi ti?t c?c m? h?nh AI ph?c v? t?ng giai ?o?n trong pipeline:

---

## 1. Story / Script Model
- **Role**: Creative Director
- **Nhi?m v?**: Ph?n t?ch ch? ?? c?ng ngh?, vi?t hook, so?n l?i tho?i ph?n ?o?n, ??nh ngh?a ? ?? th? gi?c.
- **Active Model**: Google Gemini 2.5 Pro (ho?c Gemini 2.0 Flash)
- **Status**: ACTIVE
- **Provider**: Google Cloud / DeepMind API

---

## 2. Image Generation Model
- **Role**: Scene Keyframe Generation
- **Current Direction**: Google Flow / Imagen 3
- **Status**: ACTIVE
- **Purpose**: Sinh khung h?nh 9:16 c? ?? ph?n gi?i cao, ?nh s?ng ch?n th?c, gi? v?ng nh?n di?n nh?n v?t qua 3 ?nh tham chi?u.
- **Alternative Candidates**:
  - **Flux.1 [dev]**: Kh? n?ng render ch? v? UI ch?nh x?c cao tr?n GPU ri?ng.
  - **SDXL Lightning / Turbo**: Prototyping nhanh.
  - **Qwen-Image**: M? h?nh m? ngu?n m? ?a n?ng.

---

## 3. Video Source Workflow
- **Role**: Scene source-video ingestion
- **Active source**: Manual Google Flow Ultra ZIP/folder import
- **Status**: ACTIVE; no Flow/Veo API and no browser automation
- **Current Active Fallback Engine**: `CinematicMotionEngine` (2.5D Parallax + Light Sweeps, ch?y 100% tr?n CPU)
- **Open-Source Local Alternatives**:
  - **Wan 2.2 (14B DiT)**: T?i t?o chuy?n ??ng ph?c t?p nh?t hi?n nay qua ComfyUI.
  - **LTX Video (Lightricks)**: T?c ?? sinh nhanh (g?n th?i gian th?c).
  - **Hunyuan Video (Tencent)**: Ch?t l??ng cao cho chuy?n ??ng c?nh c?ng ngh?.
  - **CogVideoX (THUDM)**: L?a ch?n c?n b?ng dung l??ng.

---

## 4. Voice Model
- **Role**: Narrator (Thuy?t minh)
- **Active Model**: `OmniVoice` (k2-fsa/OmniVoice)
- **Status**: ACTIVE
- **Purpose**: Gi?ng ??c ti?ng Vi?t t? nhi?n, ?m ?p, ??ng nh?t cao ?? v? t?c ??.
- **Reliable Fallback**: Microsoft Edge TTS (`vi-VN-NamMinhNeural` +4%)

---

## 5. Composer
- **Role**: Post-Production Engine
- **Engine**: FFmpeg
- **Status**: ACTIVE
- **Capabilities**: Concat clips, audio mixing, dynamic ducking (-14dB), burn ASS subtitles, EBU R128 loudness normalization, H.264 FastStart compression.
