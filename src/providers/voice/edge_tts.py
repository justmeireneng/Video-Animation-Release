#!/usr/bin/env python3
from pathlib import Path
from ..base import VoiceProvider, VoiceGenerationRequest
import edge_tts
import asyncio
import shutil
import subprocess

class EdgeTTSVoiceProvider(VoiceProvider):
    def __init__(self, default_voice: str = "vi-VN-NamMinhNeural"):
        self.default_voice = default_voice

    def generate_voice(self, request: VoiceGenerationRequest) -> Path:
        out_f = Path(request.output_path)
        out_f.parent.mkdir(parents=True, exist_ok=True)
        voice = request.voice_id if request.voice_id != "default" else self.default_voice
        tmp_mp3 = out_f.with_suffix(".tmp.mp3")

        async def _run():
            com = edge_tts.Communicate(request.text, voice, rate=request.rate, pitch=request.pitch)
            await com.save(str(tmp_mp3))

        asyncio.run(_run())
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            repo_root = Path(__file__).resolve().parents[3]
            candidates = sorted(repo_root.glob(
                "remotion/node_modules/**/@remotion/compositor-win32-x64-msvc/ffmpeg.exe"
            ))
            if candidates:
                ffmpeg = str(candidates[-1])
        if not ffmpeg:
            raise FileNotFoundError("ffmpeg not found in PATH or the installed Remotion compositor.")
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(tmp_mp3), "-ar", "48000", str(out_f)], check=True)
        if tmp_mp3.exists():
            tmp_mp3.unlink()
        return out_f
