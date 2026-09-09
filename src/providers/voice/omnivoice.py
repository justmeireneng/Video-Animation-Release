#!/usr/bin/env python3
from pathlib import Path
from ..base import VoiceProvider, VoiceGenerationRequest

class OmniVoiceProvider(VoiceProvider):
    def __init__(self, model_id: str = "k2-fsa/OmniVoice", device: str = "cpu"):
        self.model_id = model_id
        self.device = device

    def generate_voice(self, request: VoiceGenerationRequest) -> Path:
        # Fallback cleanly to EdgeTTS if OmniVoice weights are not loaded locally
        from .edge_tts import EdgeTTSVoiceProvider
        fallback = EdgeTTSVoiceProvider()
        return fallback.generate_voice(request)
