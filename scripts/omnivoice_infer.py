#!/usr/bin/env python3
"""One-shot, offline OmniVoice inference worker used by the desktop bridge."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: omnivoice_infer.py request.json")
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    import soundfile as sf
    import torch
    from omnivoice import OmniVoice

    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    started = time.perf_counter()
    device = str(request.get("device") or "cpu")
    model = OmniVoice.from_pretrained(
        request["model_path"], device_map=device, dtype=torch.float16, load_asr=False,
    )
    audio = model.generate(
        text=request["text"], language=request.get("language") or "vi", instruct=request.get("instruct"),
        speed=float(request.get("speed", 1.0)), num_step=int(request.get("num_step", 16)),
    )
    output = Path(request["output_path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output, audio[0], model.sampling_rate)
    print(json.dumps({
        "backend": "omnivoice_local", "device": device, "sample_rate": model.sampling_rate,
        "elapsed_seconds": round(time.perf_counter() - started, 2), "num_step": int(request.get("num_step", 16)),
    }))


if __name__ == "__main__":
    main()
