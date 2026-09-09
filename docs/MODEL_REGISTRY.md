# AI Model Registry

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

## 3. Video Generation Model (Image-to-Video)
- **Role**: Image-to-Video Animation
- **Planned Primary Candidate**: Google Flow / Veo 2 (Google Cloud Vertex AI)
- **Status**: PLANNED (Ch? m? r?ng quy?n truy c?p GA API)
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
