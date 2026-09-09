# Developer Setup Guide

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
