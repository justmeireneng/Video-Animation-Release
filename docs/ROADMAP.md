# Long-Term Development Roadmap

## Phase 2B: ZIP-first Flow sources (`v0.3.0`)

- [x] Import ZIP/folder and detect `Scene_<number>` with numeric sorting.
- [x] Map by scene index, report missing/unmatched/duplicate files, and preserve every duplicate.
- [x] Probe media, save immutable `flow_vN.mp4` versions, and support approve/reject/rollback.
- [x] Add trim, crop/focal point, transition, subtitle offset, and per-scene source-audio controls.
- [x] Compose approved video with image fallback and render fast preview/final mastered MP4.
- [x] Add a dependency-free scene review UI and project workflow state.
- [ ] Wrap the stable services in a full upload/mapping/final-review application.
- [ ] Import and review the user's real Google Flow ZIP.

## Phase 2A: Remotion cartoon composition (`v0.2.0`)

- [x] Add isolated Remotion/TypeScript runtime without replacing Python.
- [x] Add JSON-driven 1080x1920, 30fps composition and dynamic metadata.
- [x] Add four layouts, deterministic motion presets, focal-point animation, and parallax fallback.
- [x] Add mascot motion/pose resolution, phrase subtitles, narration, SFX, and transitions.
- [x] Add Studio/render commands, Python wrappers, asset review gate, and loader tests.
- [ ] Replace the current Astra photorealistic scene set with human-approved cartoon illustrations.
- [ ] Supply approved transparent assets for all eight `creator_01` mascot poses.
- [ ] Add a dedicated low-volume BGM asset and run the existing FFmpeg loudness mastering pass.

---

## Phase 1: Visual Pipeline Stabilization (HI?N T?I - `v0.1.0`)
- [x] Chuy?n ??i th?nh c?ng sang ki?n tr?c Visual-First AI Pipeline.
- [x] Thi?t l?p Global Visual Bible & H? th?ng tham chi?u 3 tr? c?t (Character, Studio, Style).
- [x] T?o b? ?nh master keyframe ch?n th?c 9:16 ??ng nh?t 100%.
- [x] Engine chuy?n ??ng 2.5D Parallax t?i ?u tr?n CPU k?t h?p Volumetric Light Sweeps.
- [x] Local Vietnamese narration through OmniVoice only; no active cloud fallback.
- [x] Ph? ?? ??ng ASS chu?n TikTok Safe Area ($Y \approx 1450\text{px}$).
- [x] Thi?t k? ?m thanh h?nh ??ng (SFX) k?t h?p Dynamic Ducking nh?c n?n (-14dB).
- [x] ??ng g?i ho?n ch?nh d? ?n m?u `Astra_AI_Explainer` (70.78s, 14.3 MB).

---

## Phase 2: Video Source Integration (`v0.2.0`)
- [x] Use manual Google Flow ZIP/folder import; API and browser automation are out of scope.
- [ ] X?y d?ng adapter ComfyUI API cho m? h?nh Wan 2.2 / LTX Video tr?n m?y ch? GPU.
- [x] Automate local mapping/versioning after a manual Flow download.
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
