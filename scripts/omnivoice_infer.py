#!/usr/bin/env python3
"""Offline OmniVoice worker used by the desktop bridge.

With ``--serve`` the model stays loaded and accepts JSON requests on stdin.
The legacy request-file mode remains useful for diagnostics.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def _runtime():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    import soundfile as sf
    import torch
    from omnivoice import OmniVoice

    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    return sf, torch, OmniVoice


def _generate(request, model, sf, *, load_seconds: float, warm_model: bool) -> dict:
    started = time.perf_counter()
    device = str(request.get("device") or "cpu")
    text = request.get("text")
    if not isinstance(text, str) or not text.strip():
        raise TypeError("text must be a non-empty string")
    language = request.get("language")
    if language is not None and not isinstance(language, str):
        raise TypeError("language must be a string or null")
    instruct = request.get("instruct")
    if instruct is not None and not isinstance(instruct, str):
        raise TypeError("instruct must be a string or null")
    ref_audio = request.get("ref_audio")
    if ref_audio is not None:
        if not isinstance(ref_audio, str) or not Path(ref_audio).is_file():
            raise FileNotFoundError(f"Reference audio was not found: {ref_audio}")
    ref_text = request.get("ref_text")
    if ref_text is not None and not isinstance(ref_text, str):
        raise TypeError("ref_text must be a string or null")
    audio = model.generate(
        text=text.strip(), language=(language or "vi").strip(), instruct=instruct.strip() if instruct else None,
        ref_audio=ref_audio, ref_text=ref_text.strip() if ref_text else None,
        speed=float(request.get("speed", 1.0)), num_step=int(request.get("num_step", 16)),
    )
    output = Path(request["output_path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output, audio[0], model.sampling_rate)
    generation_seconds = time.perf_counter() - started
    return {
        "backend": "omnivoice_local", "device": device, "sample_rate": model.sampling_rate,
        "load_seconds": round(load_seconds, 2), "generation_seconds": round(generation_seconds, 2),
        "elapsed_seconds": round(load_seconds + generation_seconds, 2),
        "num_step": int(request.get("num_step", 16)), "warm_model": warm_model,
    }


def _load_model(request, torch, OmniVoice):
    started = time.perf_counter()
    device = str(request.get("device") or "cpu")
    model = OmniVoice.from_pretrained(
        request["model_path"], device_map=device, dtype=torch.float16, load_asr=False,
    )
    return model, time.perf_counter() - started


def _serve() -> None:
    sf, torch, OmniVoice = _runtime()
    model = None
    model_key = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            requested_key = (str(request["model_path"]), str(request.get("device") or "cpu"))
            warm_model = model is not None and model_key == requested_key
            load_seconds = 0.0
            if not warm_model:
                model, load_seconds = _load_model(request, torch, OmniVoice)
                model_key = requested_key
            metrics = _generate(request, model, sf, load_seconds=load_seconds, warm_model=warm_model)
            print(json.dumps({"ok": True, "metrics": metrics}), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), flush=True)


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--serve":
        _serve()
        return
    if len(sys.argv) != 2:
        raise SystemExit("Usage: omnivoice_infer.py request.json | --serve")
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    sf, torch, OmniVoice = _runtime()
    model, load_seconds = _load_model(request, torch, OmniVoice)
    print(json.dumps(_generate(request, model, sf, load_seconds=load_seconds, warm_model=False)))


if __name__ == "__main__":
    main()
