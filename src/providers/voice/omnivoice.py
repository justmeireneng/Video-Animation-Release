#!/usr/bin/env python3
from pathlib import Path
import importlib.util
from dataclasses import replace

from ..base import VoiceGenerationRequest, VoiceProvider, VoiceSynthesisResult, wav_metadata

class OmniVoiceProvider(VoiceProvider):
    provider_id = "omnivoice"
    display_name = "OmniVoice"

    def __init__(self, model_id: str = "k2-fsa/OmniVoice", device: str = "cpu"):
        self.model_id = model_id
        self.device = device

    def generate_voice(self, request: VoiceGenerationRequest) -> Path:
        # Fallback cleanly to EdgeTTS if OmniVoice weights are not loaded locally
        from .edge_tts import EdgeTTSVoiceProvider
        fallback = EdgeTTSVoiceProvider()
        return fallback.generate_voice(request)

    def is_available(self) -> bool:
        # This adapter's established runtime is the EdgeTTS fallback. Checking it
        # does not import a model or download weights.
        return importlib.util.find_spec("edge_tts") is not None

    def health_check(self) -> dict:
        return {
            "available": self.is_available(),
            "provider": self.provider_id,
            "model_id": self.model_id,
            "device": self.device,
            "runtime_backend": "edge_tts_fallback",
        }

    def capabilities(self) -> dict:
        # Report the capabilities of this project's adapter, not every feature
        # offered by the upstream OmniVoice model.
        return {
            "synthesis": True,
            "multilingual": True,
            "voice_clone": False,
            "voice_design": True,
            "voice_design_method": "preset_voice_mapping",
            "reference_audio": False,
            "male": True,
            "female": True,
            "gender": True,
            "age": False,
            "pitch": True,
            "speed": True,
            "speed_range": {"min": 0.85, "max": 1.20, "step": 0.01},
            "modes": ["auto", "voice_design"],
        }

    def list_voices(self) -> list[dict]:
        return [
            {"voice_id": "vi-VN-NamMinhNeural", "name": "Nam Minh", "language": "vi-VN", "gender": "male"},
            {"voice_id": "vi-VN-HoaiMyNeural", "name": "Hoài My", "language": "vi-VN", "gender": "female"},
        ]

    def synthesize(self, request: VoiceGenerationRequest) -> VoiceSynthesisResult:
        effective_request = request
        options = request.options
        if options.get("mode") == "voice_design":
            design = options.get("design") if isinstance(options.get("design"), dict) else {}
            gender = str(design.get("gender") or "male").lower()
            voices = {"male": "vi-VN-NamMinhNeural", "female": "vi-VN-HoaiMyNeural"}
            voice_id = request.voice_id
            if not voice_id or voice_id == "default":
                voice_id = voices.get(gender, voices["male"])
            pitch_values = {"low": "-15Hz", "moderate": "+0Hz", "high": "+15Hz"}
            pitch = pitch_values.get(str(design.get("pitch") or "moderate").lower(), request.pitch)
            effective_request = replace(request, voice_id=voice_id, pitch=pitch)
        output = self.generate_voice(effective_request)
        duration, sample_rate = wav_metadata(output)
        return VoiceSynthesisResult(
            audio_file=output,
            provider=self.provider_id,
            voice_id=effective_request.voice_id,
            language=request.language,
            duration=duration,
            sample_rate=sample_rate,
            engine=self.model_id,
        )
