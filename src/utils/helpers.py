#!/usr/bin/env python3
from pathlib import Path
import subprocess

def format_duration(seconds: float) -> str:
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m:02d}:{s:05.2f}"

def get_media_info(path: Path | str) -> dict:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "default=noprint_wrappers=1", str(path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return {"raw": res.stdout}
