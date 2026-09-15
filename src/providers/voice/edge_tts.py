#!/usr/bin/env python3
from pathlib import Path
from ..base import VoiceGenerationRequest, VoiceProvider, VoiceSynthesisResult, wav_metadata
import edge_tts
import asyncio
import importlib.util
import shutil
import subprocess

class EdgeTTSVoiceProvider(VoiceProvider):
    provider_id = "edge_tts"
    display_name = "Edge TTS"

    def __init__(self, default_voice: str = "vi-VN-NamMinhNeural"):
        self.default_voice = default_voice

    def generate_voice(self, request: VoiceGenerationRequest) -> Path:
        out_f = Path(request.output_path)
        out_f.parent.mkdir(parents=True, exist_ok=True)
        voice = request.voice_id if request.voice_id != "default" else self.default_voice
        tmp_mp3 = out_f.with_suffix(".tmp.mp3")

        async def _run():
            for attempt in range(3):
                try:
                    com = edge_tts.Communicate(request.text, voice, rate=request.rate, pitch=request.pitch)
                    await com.save(str(tmp_mp3))
                    return
                except edge_tts.exceptions.NoAudioReceived:
                    tmp_mp3.unlink(missing_ok=True)
                    if attempt == 2:
                        raise
                    await asyncio.sleep(1.5 * (attempt + 1))

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

    def is_available(self) -> bool:
        return importlib.util.find_spec("edge_tts") is not None

    def health_check(self) -> dict:
        return {"available": self.is_available(), "backend": "edge_tts"}

    def capabilities(self) -> dict:
        return {
            "synthesis": True,
            "multilingual": True,
            "voice_clone": False,
            "voice_design": False,
            "reference_audio": False,
            "pitch": True,
            "speed": True,
        }

    def list_voices(self) -> list[dict]:
        return [{"voice_id": self.default_voice, "name": self.default_voice, "language": "vi-VN"}]

    def synthesize(self, request: VoiceGenerationRequest) -> VoiceSynthesisResult:
        output = self.generate_voice(request)
        duration, sample_rate = wav_metadata(output)
        voice_id = request.voice_id if request.voice_id != "default" else self.default_voice
        return VoiceSynthesisResult(
            audio_file=output,
            provider=self.provider_id,
            voice_id=voice_id,
            language=request.language,
            duration=duration,
            sample_rate=sample_rate,
        )
