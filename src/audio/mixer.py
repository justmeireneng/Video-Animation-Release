#!/usr/bin/env python3
"""
Audio Mixing Pipeline for Whiteboard Animation.
Mixes Voice Narration (1.0), ASMR Pen/Marker SFX (0.16), and Background Music (0.10)
with dynamic ducking when voice speaks and brickwall limiting to prevent clipping.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from .procedural_sfx import SAMPLE_RATE, _write_wav


def _get_audio_duration(path: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        try:
            return float(res.stdout.strip())
        except ValueError:
            pass
    return 60.0


def _synthesize_ambient_bgm(duration_sec: float, output_path: Path) -> Path:
    """Generate a subtle, warm ambient background tone for testing if no BGM is provided."""
    import math
    import random

    n = int(SAMPLE_RATE * duration_sec)
    samples = [0.0] * n
    # Soft warm pads (major chords in A major: A2, E3, C#4)
    freqs = [110.0, 164.81, 277.18]
    for f in freqs:
        for i in range(n):
            t = i / SAMPLE_RATE
            # Slow breathing LFO
            lfo = 0.5 + 0.5 * math.sin(2.0 * math.pi * 0.2 * t)
            samples[i] += 0.25 * math.sin(2.0 * math.pi * f * t) * lfo

    # Gentle vinyl crackle / warmth
    rng = random.Random(99)
    for i in range(n):
        if rng.random() < 0.002:
            samples[i] += rng.uniform(-0.15, 0.15)

    _write_wav(output_path, samples)
    return output_path


def mix_project_audio(
    narration_path: Path | str,
    asmr_path: Path | str,
    output_path: Path | str,
    bgm_path: Path | str | None = None,
    config: dict[str, Any] | None = None,
) -> Path:
    """
    Mix narration, ASMR pen sound, and BGM into final_audio.wav.
    """
    narr_file = Path(narration_path)
    asmr_file = Path(asmr_path)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if not narr_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file narration: {narr_file}")
    if not asmr_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file ASMR: {asmr_file}")

    cfg = config or {}
    audio_cfg = cfg.get("audio_mix", {})
    v_narr = float(audio_cfg.get("narration_volume", 1.0))
    v_asmr = float(audio_cfg.get("asmr_pen_volume", 0.16))
    v_bgm = float(audio_cfg.get("bgm_volume", 0.10))

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Yêu cầu FFmpeg trong PATH để thực hiện mix âm thanh.")

    has_bgm = False
    bgm_file: Path | None = None
    if bgm_path:
        p = Path(bgm_path)
        if p.exists():
            bgm_file = p
            has_bgm = True
        else:
            print(f"  [warn] File BGM không tồn tại: {p}, bỏ qua BGM.")

    print("=" * 56)
    print("BẮT ĐẦU MIX AUDIO")
    print(f"  Voice     : {narr_file.name} (vol={v_narr})")
    print(f"  ASMR Pen  : {asmr_file.name} (vol={v_asmr})")
    if has_bgm and bgm_file:
        print(f"  BGM       : {bgm_file.name} (vol={v_bgm} có ducking)")
    print(f"  Output    : {out_file.name}")
    print("=" * 56)

    target_dur = max(_get_audio_duration(narr_file), _get_audio_duration(asmr_file))

    # Construct ffmpeg filter complex
    if has_bgm and bgm_file:
        # 3 inputs: 0=voice, 1=asmr, 2=bgm (looped)
        filter_str = (
            f"[0:a]volume={v_narr},asplit=2[v_main][v_side];"
            f"[1:a]volume={v_asmr}[asmr_in];"
            f"[2:a]volume={v_bgm}[bgm_raw];"
            f"[bgm_raw][v_side]sidechaincompress=threshold=0.08:ratio=4:attack=50:release=300[bgm_ducked];"
            f"[v_main][asmr_in][bgm_ducked]amix=inputs=3:duration=longest:dropout_transition=0,"
            f"alimiter=limit=0.95[out]"
        )
        cmd = [
            ffmpeg, "-y", "-loglevel", "error",
            "-i", str(narr_file),
            "-i", str(asmr_file),
            "-stream_loop", "-1", "-i", str(bgm_file),
            "-filter_complex", filter_str,
            "-map", "[out]",
            "-t", f"{target_dur:.3f}",
            "-c:a", "pcm_s16le",
            str(out_file),
        ]
    else:
        # 2 inputs: 0=voice, 1=asmr
        filter_str = (
            f"[0:a]volume={v_narr}[v_in];"
            f"[1:a]volume={v_asmr}[asmr_in];"
            f"[v_in][asmr_in]amix=inputs=2:duration=longest:dropout_transition=0,"
            f"alimiter=limit=0.95[out]"
        )
        cmd = [
            ffmpeg, "-y", "-loglevel", "error",
            "-i", str(narr_file),
            "-i", str(asmr_file),
            "-filter_complex", filter_str,
            "-map", "[out]",
            "-t", f"{target_dur:.3f}",
            "-c:a", "pcm_s16le",
            str(out_file),
        ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Lỗi khi mix audio bằng FFmpeg: {res.stderr}")

    print(f"[ok] Đã tạo file mix thành công: {out_file}")
    return out_file


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Sử dụng: python mixer.py <voice.wav> <asmr.wav> <output.wav> [bgm.mp3]")
        sys.exit(1)
    bgm = sys.argv[4] if len(sys.argv) > 4 else None
    mix_project_audio(sys.argv[1], sys.argv[2], sys.argv[3], bgm)
