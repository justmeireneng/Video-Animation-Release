# Model Download & Management Guide

> **QUY T?C QUAN TR?NG**: Tuy?t ??i **KH?NG** commit c?c t?p tr?ng s? m? h?nh l?n (`.pt`, `.pth`, `.bin`, `.safetensors`, `.ckpt`) l?n kho l?u tr? Git. H?y s? d?ng Git LFS ho?c script t?i ri?ng bi?t.

---

## 1. Danh M?c M? H?nh C?c B? (Local Models)

| M? h?nh | Nh? ph?t tri?n | Phi?n b?n | Dung l??ng | Ngu?n t?i |
|---|---|---|---|---|
| **OmniVoice** | k2-fsa | Main | ~1.5 GB | [HuggingFace: k2-fsa/OmniVoice](https://huggingface.co/k2-fsa/OmniVoice) |
| **Wan 2.2 (14B)** | Wan-Video | 2.2 | ~28 GB | [HuggingFace: Wan-AI/Wan2.2-T2V-14B](https://huggingface.co/) |
| **LTX-Video** | Lightricks | 0.9.1 | ~4.5 GB | [HuggingFace: Lightricks/LTX-Video](https://huggingface.co/) |

---

## 2. H??ng D?n T?i & C?i ??t OmniVoice (T?y Ch?n)
OmniVoice is the only active voice provider. Its runtime and model are installed separately from the app; the app never downloads weights at startup and never falls back to an online voice service.

```bash
# C?i ??t git-lfs
git lfs install

# T?i tr?ng s? v?o th? m?c models/ (th? m?c n?y ?? ???c .gitignore b? qua)
mkdir -p models
cd models
git clone https://huggingface.co/k2-fsa/OmniVoice
```
Trong `.env`, c?u h?nh:
```env
OMNIVOICE_MODEL_ID=models/OmniVoice
OMNIVOICE_DEVICE=cpu
```
