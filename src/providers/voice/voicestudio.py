#!/usr/bin/env python3
"""Optional VoiceStudio adapter using its local OpenAI-compatible REST API."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from ..base import VoiceGenerationRequest, VoiceProvider, VoiceSynthesisResult, wav_metadata


class VoiceStudioProvider(VoiceProvider):
    provider_id = "voicestudio"
    display_name = "VoiceStudio"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 2.0,
    ):
        self.base_url = (base_url or os.getenv("VOICESTUDIO_BASE_URL") or "http://127.0.0.1:3900").rstrip("/") + "/"
        self.api_key = api_key or os.getenv("VOICESTUDIO_API_KEY") or os.getenv("OMNIVOICE_API_KEY")
        self.timeout = timeout

    def _headers(self, *, json_body: bool = False) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if json_body:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _json(self, path: str) -> dict[str, Any]:
        request = Request(urljoin(self.base_url, path.lstrip("/")), headers=self._headers())
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {"items": payload}

    def is_available(self) -> bool:
        return bool(self.health_check()["available"])

    def health_check(self) -> dict[str, Any]:
        try:
            payload = self._json("health")
            return {
                "available": True,
                "provider": self.provider_id,
                "base_url": self.base_url.rstrip("/"),
                "status": payload.get("status", "ok"),
                "version": payload.get("version"),
            }
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            return {
                "available": False,
                "provider": self.provider_id,
                "base_url": self.base_url.rstrip("/"),
                "status": "not_installed_or_not_running",
                "detail": str(exc),
            }

    def capabilities(self) -> dict[str, Any]:
        return {
            "synthesis": True,
            "multilingual": True,
            "voice_clone": True,
            "voice_clone_method": "saved_voice_profile",
            "voice_design": True,
            "voice_design_scope": "engine_dependent",
            "reference_audio": False,
            "reference_audio_note": "Create a VoiceStudio voice profile first, then pass its voice_id.",
            "pitch": "engine_dependent",
            "speed": True,
            "speed_range": {"min": 0.85, "max": 1.20, "step": 0.01},
            "engine_discovery": True,
            "modes": ["auto", "voice_design", "voice_clone"],
        }

    def _catalog(self) -> dict[str, Any]:
        return self._json("v1/audio/voices")

    def list_voices(self) -> list[dict[str, Any]]:
        try:
            voices = self._catalog().get("voices", [])
            return [voice for voice in voices if isinstance(voice, dict)]
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            return []

    def list_engines(self) -> list[dict[str, Any]]:
        """Discover engines from the running service; never mirror README lists."""

        try:
            engines = self._catalog().get("engines", [])
            if isinstance(engines, dict):
                return [dict(value, engine_id=key) if isinstance(value, dict) else {"engine_id": key, "value": value}
                        for key, value in engines.items()]
            return [item if isinstance(item, dict) else {"engine_id": str(item)} for item in engines]
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            return []

    @staticmethod
    def _design_description(options: dict[str, Any]) -> str | None:
        if options.get("description"):
            return str(options["description"])
        design = options.get("design")
        if not isinstance(design, dict):
            return None
        values = [str(design[key]).strip() for key in ("gender", "age", "pitch") if design.get(key)]
        return ", ".join(values) or None

    def synthesize(self, request: VoiceGenerationRequest) -> VoiceSynthesisResult:
        options = request.options
        if request.ref_audio and request.voice_id == "default":
            raise ValueError(
                "VoiceStudio's /v1/audio/speech endpoint accepts saved voice profile IDs, "
                "not direct reference-audio uploads. Create a profile in VoiceStudio first."
            )
        speed = float(options.get("speed", 1.0))
        payload: dict[str, Any] = {
            "model": str(options.get("engine") or options.get("model") or "tts-1"),
            "input": request.text,
            "voice": request.voice_id or "default",
            "response_format": "wav",
            "speed": speed,
            # The upstream extension documents ISO 639-1; accept project locales
            # such as vi-VN while sending their base language to VoiceStudio.
            "language": request.language.split("-", 1)[0],
        }
        if options.get("mode") == "voice_design":
            description = self._design_description(options)
            if description:
                payload["description"] = description
        for key in ("instruct", "duration", "seed", "denoise", "preprocess_prompt", "chunk_duration",
                    "chunk_threshold", "num_step", "guidance_scale"):
            if key in options:
                payload[key] = options[key]

        output = Path(request.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = Request(
            urljoin(self.base_url, "v1/audio/speech"),
            data=body,
            headers=self._headers(json_body=True),
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=max(self.timeout, 30.0)) as response:
                audio = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            retry = " (retry later)" if exc.code in (429, 503) else ""
            raise RuntimeError(f"VoiceStudio synthesis failed: HTTP {exc.code}{retry}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"VoiceStudio is unavailable at {self.base_url.rstrip('/')}: {exc}") from exc
        output.write_bytes(audio)
        duration, sample_rate = wav_metadata(output)
        return VoiceSynthesisResult(
            audio_file=output,
            provider=self.provider_id,
            voice_id=request.voice_id,
            language=request.language,
            duration=duration,
            sample_rate=sample_rate,
            timing=None,
            engine=str(payload["model"]),
        )
