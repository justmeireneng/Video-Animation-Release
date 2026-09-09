# Long-Term Development Roadmap

---

## Phase 1: Visual Pipeline Stabilization (HI?N T?I - `v0.1.0`)
- [x] Chuy?n ??i th?nh c?ng sang ki?n tr?c Visual-First AI Pipeline.
- [x] Thi?t l?p Global Visual Bible & H? th?ng tham chi?u 3 tr? c?t (Character, Studio, Style).
- [x] T?o b? ?nh master keyframe ch?n th?c 9:16 ??ng nh?t 100%.
- [x] Engine chuy?n ??ng 2.5D Parallax t?i ?u tr?n CPU k?t h?p Volumetric Light Sweeps.
- [x] T?ch h?p thuy?t minh ti?ng Vi?t chu?n x?c (OmniVoice / EdgeTTS).
- [x] Ph? ?? ??ng ASS chu?n TikTok Safe Area ($Y \approx 1450\text{px}$).
- [x] Thi?t k? ?m thanh h?nh ??ng (SFX) k?t h?p Dynamic Ducking nh?c n?n (-14dB).
- [x] ??ng g?i ho?n ch?nh d? ?n m?u `Astra_AI_Explainer` (70.78s, 14.3 MB).

---

## Phase 2: Video Generation Backend Integration (`v0.2.0`)
- [ ] T?ch h?p Google Cloud Vertex AI Veo 2 API khi c? quy?n truy c?p GA.
- [ ] X?y d?ng adapter ComfyUI API cho m? h?nh Wan 2.2 / LTX Video tr?n m?y ch? GPU.
- [ ] T? ??ng h?a qu? tr?nh ??ng g?i v? nh?p l?i video t? Google Flow web.
- [ ] Thu?t to?n kh? rung (RIFE) v? n?ng n?t khung h?nh (Real-ESRGAN).

---

## Phase 3: AI Video Studio Web Application (`v0.3.0`)
- [ ] X?y d?ng Web UI (Next.js / FastAPI) cho ng??i s?ng t?o n?i dung:
  - Tr?nh duy?t v? ch?nh s?a Storyboard Contact Sheet tr?c quan.
  - T?i t?o (regenerate) t?ng shot b?ng prompt t?y ch?nh.
  - Tr?nh ph?t video preview t?ng ph?n ?o?n k?m timeline ?m thanh.
  - Xu?t b?n 1-click video ?a n?n t?ng (TikTok, Shorts, Reels).

---

## Phase 4: Production Cloud & Docker Deployment (`v1.0.0`)
- [ ] ??ng g?i to?n b? h? sinh th?i th?nh Docker Compose (Web UI, API Backend, Celery/Redis GPU Worker, FFmpeg Render Node).
- [ ] H? th?ng gi?m s?t chi ph? API v? c?nh b?o quota t? ??ng.
