#!/usr/bin/env python3
"""
ASMR Sound Effects Generator for Whiteboard Animation.
Processes stroke_event_timeline.json and generates synchronized, organic
pencil/marker sound effects with jitter, gain variation, crossfade tiling,
and anti-monotony randomized slicing.
"""
from __future__ import annotations

import json
import math
import random
import struct
import sys
import wave
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from .procedural_sfx import ensure_sfx_assets, SAMPLE_RATE, _clamp


def _db_to_linear(db: float) -> float:
    return math.pow(10.0, db / 20.0)


def load_wav(path: Path) -> tuple[int, list[float]]:
    """Read mono or stereo 16-bit PCM WAV, return (sample_rate, samples_float)."""
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        n_ch = wf.getnchannels()
        n_frames = wf.getnframes()
        sampwidth = wf.getsampwidth()
        raw = wf.readframes(n_frames)

    if sampwidth != 2:
        raise ValueError(f"Chỉ hỗ trợ 16-bit PCM WAV (file: {path.name} có sampwidth={sampwidth})")

    fmt = f"<{n_frames * n_ch}h"
    ints = struct.unpack(fmt, raw)
    if n_ch == 1:
        samples = [s / 32768.0 for s in ints]
    else:
        # Downmix stereo to mono
        samples = [(ints[i * 2] + ints[i * 2 + 1]) / 65536.0 for i in range(n_frames)]

    return sr, samples


def save_wav(path: Path, samples: list[float], sr: int = SAMPLE_RATE) -> None:
    """Save normalized mono 16-bit PCM WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = max((abs(s) for s in samples), default=0.0)
    # Normalize if exceeding 0.95
    scale = 0.95 / peak if peak > 0.95 else 1.0

    raw_bytes = bytearray()
    for s in samples:
        val = int(_clamp(s * scale) * 32767.0)
        raw_bytes.extend(struct.pack("<h", val))

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(raw_bytes)


class SFXAssetPool:
    """Manages audio samples and fallbacks."""

    def __init__(self, asset_dir: Path | str):
        self.asset_dir = Path(asset_dir)
        self.samples: dict[str, list[float]] = {}
        self.sample_rates: dict[str, int] = {}
        self._ensure_and_load()

    def _ensure_and_load(self) -> None:
        # Guarantee assets exist (generate procedural if missing)
        ensure_sfx_assets(self.asset_dir)

        wav_files = list(self.asset_dir.glob("*.wav"))
        for wf in wav_files:
            try:
                sr, samps = load_wav(wf)
                self.samples[wf.name] = samps
                self.sample_rates[wf.name] = sr
            except Exception as e:
                print(f"  [warn] Lỗi tải SFX {wf.name}: {e}")

    def get_sample(self, candidate_names: list[str]) -> list[float]:
        """Get one sample from candidates with fallback."""
        available = [name for name in candidate_names if name in self.samples and len(self.samples[name]) > 0]
        if available:
            chosen = random.choice(available)
            return self.samples[chosen]

        # Fallback to any available sound
        if self.samples:
            fallback_key = next(iter(self.samples))
            print(f"  [warn] Không tìm thấy SFX trong {candidate_names}, fallback dùng {fallback_key}")
            return self.samples[fallback_key]

        print("  [warn] Không có sample nào trong pool, dùng silence.")
        return []


def generate_event_audio(
    raw_sample: list[float],
    target_samples: int,
    fade_samples: int,
    gain: float,
    rng: random.Random,
) -> list[float]:
    """
    Slices and crossfade-tiles an audio sample to fit target_samples duration.
    Randomizes starting offset to avoid mechanical repetition.
    Applies fade-in and fade-out to prevent clicks.
    """
    if not raw_sample or target_samples <= 0:
        return [0.0] * target_samples

    sample_len = len(raw_sample)
    out = [0.0] * target_samples

    # If sample is longer than target, take a random chunk
    if sample_len >= target_samples:
        max_start = sample_len - target_samples
        start_idx = rng.randint(0, max_start)
        for i in range(target_samples):
            out[i] = raw_sample[start_idx + i] * gain
    else:
        # Crossfade tiling when target duration exceeds sample duration
        pos = 0
        while pos < target_samples:
            chunk_len = min(sample_len, target_samples - pos)
            start_idx = rng.randint(0, max(0, sample_len - chunk_len))
            for i in range(chunk_len):
                out[pos + i] = raw_sample[start_idx + i] * gain
            pos += chunk_len

    # Apply cosine ramp fade-in and fade-out
    f_in = min(fade_samples, target_samples // 2)
    f_out = min(fade_samples, target_samples // 2)

    for i in range(f_in):
        factor = 0.5 * (1.0 - math.cos(math.pi * i / f_in))
        out[i] *= factor

    for i in range(f_out):
        idx = target_samples - 1 - i
        factor = 0.5 * (1.0 - math.cos(math.pi * i / f_out))
        out[idx] *= factor

    return out


def generate_asmr_track(
    timeline_path: Path | str,
    output_path: Path | str,
    project_config: dict[str, Any] | None = None,
) -> Path:
    """
    Generate master asmr_pen.wav synchronized to stroke_event_timeline.json.
    """
    timeline_file = Path(timeline_path)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if not timeline_file.exists():
        raise FileNotFoundError(f"Không tìm thấy timeline: {timeline_file}")

    events = json.loads(timeline_file.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise ValueError("stroke_event_timeline.json phải là danh sách các event.")

    cfg = project_config or {}
    asmr_cfg = cfg.get("asmr", {})
    if not asmr_cfg.get("enabled", True):
        print("  [sfx] ASMR bị vô hiệu hóa trong cấu hình.")
        # Create 1 second silent wav
        save_wav(out_file, [0.0] * SAMPLE_RATE)
        return out_file

    asset_dir = Path(asmr_cfg.get("asset_dir", "assets/sfx"))
    if not asset_dir.is_absolute():
        asset_dir = Path(__file__).resolve().parent.parent.parent / asset_dir

    master_volume = float(asmr_cfg.get("volume", 0.16))
    random_gain_db = float(asmr_cfg.get("random_gain_db", 2.0))
    timing_jitter_ms = int(asmr_cfg.get("timing_jitter_ms", 30))
    fade_ms = int(asmr_cfg.get("fade_ms", 50))

    fade_samples = int(fade_ms * SAMPLE_RATE / 1000)
    jitter_samples_max = int(timing_jitter_ms * SAMPLE_RATE / 1000)

    pool = SFXAssetPool(asset_dir)
    rng = random.Random(42)

    # Calculate total duration needed
    max_end_ms = 0
    for ev in events:
        end_ms = ev.get("start_ms", 0) + ev.get("duration_ms", 0)
        if end_ms > max_end_ms:
            max_end_ms = end_ms

    total_samples = int(math.ceil((max_end_ms + 600) * SAMPLE_RATE / 1000))
    master_track = [0.0] * max(SAMPLE_RATE, total_samples)

    mapped_stats: dict[str, int] = {}

    for ev in events:
        ev_type = ev.get("type", "pause")
        start_ms = ev.get("start_ms", 0)
        dur_ms = ev.get("duration_ms", 0)
        intensity = float(ev.get("intensity", 0.8))

        # TRAVEL, PAUSE, and SILENCE events produce zero sound
        if ev_type in ("pause", "travel", "silence") or dur_ms <= 0:
            continue

        # Map event type to SFX files
        if ev_type in ("ink_stroke", "pencil_soft"):
            sound_candidates = ["pencil_soft_01.wav", "pencil_soft_02.wav"]
            mapped_key = "pencil_soft"
        elif ev_type in ("fast_stroke", "pencil_fast"):
            sound_candidates = ["pencil_fast_01.wav"]
            mapped_key = "pencil_fast"
        elif ev_type in ("color_fill", "marker_fill"):
            sound_candidates = ["marker_fill_01.wav"]
            mapped_key = "marker_fill"
        elif ev_type in ("gesture", "arrow", "circle", "marker_soft"):
            sound_candidates = ["marker_soft_01.wav", "paper_swipe_01.wav"]
            mapped_key = "marker_soft"
        else:
            sound_candidates = ["pencil_soft_01.wav"]
            mapped_key = "pencil_soft"

        mapped_stats[mapped_key] = mapped_stats.get(mapped_key, 0) + 1

        # Apply timing jitter
        jitter = rng.randint(-jitter_samples_max, jitter_samples_max) if jitter_samples_max > 0 else 0
        target_start_sample = max(0, int(start_ms * SAMPLE_RATE / 1000) + jitter)
        target_len_samples = int(dur_ms * SAMPLE_RATE / 1000)

        # Apply gain variation
        gain_db = rng.uniform(-random_gain_db, random_gain_db)
        gain_linear = _db_to_linear(gain_db) * master_volume * intensity

        raw_sample = pool.get_sample(sound_candidates)
        event_audio = generate_event_audio(
            raw_sample, target_len_samples, fade_samples, gain_linear, rng
        )

        # Mix into master track
        for i, val in enumerate(event_audio):
            idx = target_start_sample + i
            if idx < len(master_track):
                master_track[idx] += val

    save_wav(out_file, master_track)
    total_dur_sec = len(master_track) / SAMPLE_RATE

    print("=" * 56)
    print("ASMR SFX GENERATOR HOÀN TẤT")
    print("=" * 56)
    print(f"  Input Timeline: {timeline_file}")
    print(f"  Output Audio  : {out_file}")
    print(f"  Tổng thời lượng : {total_dur_sec:.2f}s ({len(master_track)} samples)")
    print(f"  Thống kê events: {len(events)} events tổng cộng")
    for k, cnt in mapped_stats.items():
        print(f"    - {k}: {cnt} lần")
    print("=" * 56)

    return out_file


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Sử dụng: python sfx_generator.py <timeline.json> <output.wav>")
        sys.exit(1)
    generate_asmr_track(sys.argv[1], sys.argv[2])
