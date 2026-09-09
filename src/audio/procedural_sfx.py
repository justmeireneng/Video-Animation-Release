#!/usr/bin/env python3
"""
Procedural ASMR Sound Synthesizer for Whiteboard Animation.
Generates realistic pencil and marker audio textures using filtered noise
and amplitude modulation, without requiring external audio libraries.
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 44100


def _clamp(v: float, min_v: float = -1.0, max_v: float = 1.0) -> float:
    return max(min_v, min(max_v, v))


def _apply_biquad(samples: list[float], b0: float, b1: float, b2: float, a1: float, a2: float) -> list[float]:
    """Apply direct form I biquad IIR filter."""
    out = [0.0] * len(samples)
    x1 = x2 = y1 = y2 = 0.0
    for i, x in enumerate(samples):
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1 = x1, x
        y2, y1 = y1, y
        out[i] = y
    return out


def _bandpass_filter(samples: list[float], center_freq: float, q: float = 1.5, sr: int = SAMPLE_RATE) -> list[float]:
    """Digital biquad bandpass filter with constant skirt gain."""
    w0 = 2.0 * math.pi * center_freq / sr
    alpha = math.sin(w0) / (2.0 * q)
    b0 = alpha
    b1 = 0.0
    b2 = -alpha
    a0 = 1.0 + alpha
    a1 = -2.0 * math.cos(w0)
    a2 = 1.0 - alpha
    return _apply_biquad(samples, b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def _lowpass_filter(samples: list[float], cutoff: float, q: float = 0.707, sr: int = SAMPLE_RATE) -> list[float]:
    """Digital biquad lowpass filter."""
    w0 = 2.0 * math.pi * cutoff / sr
    alpha = math.sin(w0) / (2.0 * q)
    cos_w0 = math.cos(w0)
    b0 = (1.0 - cos_w0) / 2.0
    b1 = 1.0 - cos_w0
    b2 = (1.0 - cos_w0) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha
    return _apply_biquad(samples, b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def _highpass_filter(samples: list[float], cutoff: float, q: float = 0.707, sr: int = SAMPLE_RATE) -> list[float]:
    """Digital biquad highpass filter."""
    w0 = 2.0 * math.pi * cutoff / sr
    alpha = math.sin(w0) / (2.0 * q)
    cos_w0 = math.cos(w0)
    b0 = (1.0 + cos_w0) / 2.0
    b1 = -(1.0 + cos_w0)
    b2 = (1.0 + cos_w0) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha
    return _apply_biquad(samples, b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def _write_wav(path: Path, samples: list[float], sr: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Normalize peak to 0.90 to avoid clipping
    peak = max(abs(s) for s in samples) if samples else 1.0
    scale = 0.90 / peak if peak > 1e-5 else 1.0

    raw_bytes = bytearray()
    for s in samples:
        val = int(_clamp(s * scale) * 32767.0)
        raw_bytes.extend(struct.pack("<h", val))

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(raw_bytes)


def synthesize_pencil_soft(duration_sec: float = 3.0, seed: int = 42) -> list[float]:
    """Synthesize gentle pencil scratching on paper (continuous stroke)."""
    rng = random.Random(seed)
    n = int(SAMPLE_RATE * duration_sec)
    noise = [rng.uniform(-1.0, 1.0) for _ in range(n)]
    bp = _bandpass_filter(noise, center_freq=2200.0, q=1.2)
    out = []
    for i, s in enumerate(bp):
        t = i / SAMPLE_RATE
        mod = 0.7 + 0.25 * math.sin(2.0 * math.pi * 12.0 * t) + 0.15 * math.sin(2.0 * math.pi * 31.0 * t)
        out.append(s * mod)
    return out


def synthesize_pencil_fast(duration_sec: float = 2.0, seed: int = 101) -> list[float]:
    """Synthesize rapid, sharp pencil sketching strokes."""
    rng = random.Random(seed)
    n = int(SAMPLE_RATE * duration_sec)
    noise = [rng.uniform(-1.0, 1.0) for _ in range(n)]
    bp = _bandpass_filter(noise, center_freq=3400.0, q=1.6)
    out = []
    stroke_rate = 8.0  # 8 rapid strokes per second
    for i, s in enumerate(bp):
        t = i / SAMPLE_RATE
        burst = math.pow(max(0.0, math.sin(2.0 * math.pi * stroke_rate * t)), 2.5)
        mod = 0.25 + 0.85 * burst
        out.append(s * mod)
    return out


def synthesize_marker_soft(duration_sec: float = 2.5, seed: int = 202) -> list[float]:
    """Synthesize felt-tip marker drawing with slight paper friction and squeak."""
    rng = random.Random(seed)
    n = int(SAMPLE_RATE * duration_sec)
    noise = [rng.uniform(-1.0, 1.0) for _ in range(n)]
    bp = _bandpass_filter(noise, center_freq=1100.0, q=2.0)
    out = []
    for i, s in enumerate(bp):
        t = i / SAMPLE_RATE
        mod = 0.75 + 0.2 * math.sin(2.0 * math.pi * 6.5 * t)
        squeak = 0.05 * math.sin(2.0 * math.pi * 1850.0 * t) * (1.0 if math.sin(2.0 * math.pi * 1.5 * t) > 0.8 else 0.0)
        out.append(s * mod + squeak)
    return out


def synthesize_marker_fill(duration_sec: float = 3.5, seed: int = 303) -> list[float]:
    """Synthesize back-and-forth coloring / shading marker texture."""
    rng = random.Random(seed)
    n = int(SAMPLE_RATE * duration_sec)
    noise = [rng.uniform(-1.0, 1.0) for _ in range(n)]
    bp = _bandpass_filter(noise, center_freq=850.0, q=1.4)
    out = []
    sweep_rate = 3.2  # 3.2 sweeps per second
    for i, s in enumerate(bp):
        t = i / SAMPLE_RATE
        envelope = 0.35 + 0.65 * math.pow(abs(math.sin(2.0 * math.pi * sweep_rate * t)), 1.2)
        out.append(s * envelope)
    return out


def synthesize_paper_swipe(duration_sec: float = 0.6, seed: int = 404) -> list[float]:
    """Synthesize short paper swipe / gesture swoosh."""
    rng = random.Random(seed)
    n = int(SAMPLE_RATE * duration_sec)
    noise = [rng.uniform(-1.0, 1.0) for _ in range(n)]
    lp = _lowpass_filter(noise, cutoff=1400.0)
    out = []
    for i, s in enumerate(lp):
        t = i / n
        env = math.sin(math.pi * t) ** 1.8
        out.append(s * env)
    return out


DEFAULT_ASSETS = {
    "pencil_soft_01.wav": lambda: synthesize_pencil_soft(3.0, seed=42),
    "pencil_soft_02.wav": lambda: synthesize_pencil_soft(3.0, seed=43),
    "pencil_fast_01.wav": lambda: synthesize_pencil_fast(2.5, seed=101),
    "marker_soft_01.wav": lambda: synthesize_marker_soft(2.5, seed=202),
    "marker_fill_01.wav": lambda: synthesize_marker_fill(3.5, seed=303),
    "paper_swipe_01.wav": lambda: synthesize_paper_swipe(0.6, seed=404),
}


def ensure_sfx_assets(asset_dir: Path | str) -> dict[str, Path]:
    """Ensure all required ASMR sound files exist, generating procedural ones if missing."""
    target_dir = Path(asset_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    out_map: dict[str, Path] = {}

    for filename, synth_fn in DEFAULT_ASSETS.items():
        file_path = target_dir / filename
        if not file_path.exists() or file_path.stat().st_size == 0:
            samples = synth_fn()
            _write_wav(file_path, samples)
            print(f"  [sfx] Đã tạo procedural audio: {file_path.name} ({len(samples)/SAMPLE_RATE:.1f}s)")
        out_map[filename] = file_path

    return out_map


if __name__ == "__main__":
    sfx_dir = Path(__file__).resolve().parent.parent.parent / "assets" / "sfx"
    print(f"Kiểm tra và tạo bộ âm thanh ASMR tại: {sfx_dir}")
    created = ensure_sfx_assets(sfx_dir)
    print(f"Đã sẵn sàng {len(created)} file SFX.")
