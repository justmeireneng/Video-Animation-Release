# Developer Setup Guide

## ZIP-first commands

```bash
python app.py import-flow-zip Astra_AI_Explainer path/to/flow.zip
python app.py import-flow-folder Astra_AI_Explainer path/to/flow-folder
python app.py review-scene-video Astra_AI_Explainer --scene scene_01
python app.py render-preview Astra_AI_Explainer
python app.py render-video Astra_AI_Explainer
```

`ffprobe` and `ffmpeg` may come from PATH or the installed Remotion compositor. Imported clips
remain pending until approved; no Flow/Veo credentials or browser automation are required.

## Remotion runtime (v0.2)

Prerequisites: Node.js 16 or newer (Node 20+ recommended), pnpm, and a Chromium-compatible
local rendering environment. The verified machine uses Node `24.19.0` and pnpm `11.19.0`.
Python dependencies are unchanged.

```bash
cd remotion
pnpm install
pnpm run typecheck
pnpm test
pnpm run build
cd ..
pnpm run remotion:studio
pnpm run remotion:test-render
```

Equivalent npm-facing root commands are `npm run remotion:studio` and
`npm run remotion:render` when npm is available. Python wrappers are:

```bash
python app.py preview-video Astra_AI_Explainer
python app.py render-preview Astra_AI_Explainer
python app.py render-video Astra_AI_Explainer
```

Studio reads `projects/Astra_AI_Explainer/remotion.json`, supports timeline scrubbing, and
previews the same data used by CLI rendering. On low-power machines, keep render concurrency
at `1` or `25%` and retain the 1080x1920/30fps target.

H??ng d?n chi ti?t thi?t l?p m?i tr??ng ph?t tri?n ??c l?p (ho?n to?n kh?ng ph? thu?c Antigravity):

---

## 1. Y?u C?u Ti?n Quy?t (Prerequisites)
1. **Python**: Phi?n b?n 3.10, 3.11 ho?c 3.12 (khuy?n ngh? 3.11).
2. **FFmpeg**: ?? c?i ??t v? th?m v?o bi?n m?i tr??ng h? th?ng (`PATH`).
   - Ki?m tra b?ng l?nh: `ffmpeg -version` v? `ffprobe -version`.
3. **Git**: ?? c?i ??t Git CLI.

---

## 2. C?c B??c C?i ??t (Step-by-Step Setup)

### B??c 1: Sao ch?p m? ngu?n
```bash
git clone https://github.com/your-username/video-animation.git
cd video-animation
```

### B??c 2: Kh?i t?o Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### B??c 3: C?i ??t th? vi?n ph? thu?c
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### B??c 4: Thi?t l?p bi?n m?i tr??ng
Sao ch?p t?p c?u h?nh m?u v? ?i?n API keys c?a b?n:
```bash
cp .env.example .env
```

### B??c 5: Ch?y ki?m th? h? th?ng
```bash
# Ki?m tra tr?ng th?i d? ?n m?u
python app.py status Astra_AI_Explainer

# Ch?y b? unit tests
python -m unittest discover -s tests
```
