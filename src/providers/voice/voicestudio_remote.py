#!/usr/bin/env python3
"""Remote-only VoiceStudio adapter for its OpenAI-compatible audio API.

This module deliberately does not start VoiceStudio, install models, or use a
local VoiceStudio endpoint. Inference belongs to the configured remote host.
"""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from ..base import VoiceGenerationRequest, VoiceProvider, VoiceSynthesisResult, wav_metadata


class RemoteVoiceStudioConfigurationError(ValueError):
    """Raised when a VoiceStudio Remote endpoint breaks the remote-only boundary."""


class RemoteVoiceStudioProvider(VoiceProvider):
    provider_id = "voicestudio_remote"
    display_name = "VoiceStudio Remote"
    default_timeout_seconds = 180.0

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self._opener = opener or urlopen
        self.base_url: str | None = None
        self.api_key: str | None = None
        self.timeout_seconds = self.default_timeout_seconds
        self.last_metrics: dict[str, Any] | None = None
        self.configure(base_url=base_url, api_key=api_key, timeout_seconds=timeout_seconds)

    def configure(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> "RemoteVoiceStudioProvider":
        """Apply transient connection settings without persisting any secret."""

        raw_url = base_url if base_url is not None else os.getenv("VOICESTUDIO_BASE_URL")
        self.base_url = raw_url.strip() if isinstance(raw_url, str) and raw_url.strip() else None
        raw_key = api_key if api_key is not None else os.getenv("VOICESTUDIO_API_KEY")
        self.api_key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None
        raw_timeout = timeout_seconds if timeout_seconds is not None else os.getenv("VOICESTUDIO_TIMEOUT_SECONDS")
        try:
            self.timeout_seconds = float(raw_timeout) if raw_timeout is not None else self.default_timeout_seconds
        except (TypeError, ValueError):
            self.timeout_seconds = self.default_timeout_seconds
        if self.timeout_seconds <= 0:
            self.timeout_seconds = self.default_timeout_seconds
        return self

    def _validated_base_url(self) -> str:
        if not self.base_url:
            raise RemoteVoiceStudioConfigurationError(
                "VoiceStudio Remote requires VOICESTUDIO_BASE_URL; local endpoints are intentionally disabled."
            )
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise RemoteVoiceStudioConfigurationError("VoiceStudio Remote URL must be a complete http:// or https:// URL.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise RemoteVoiceStudioConfigurationError("VoiceStudio Remote URL must not contain credentials, query parameters, or fragments.")
        host = parsed.hostname.lower()
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = host == "localhost" or host.endswith(".localhost")
        if is_loopback:
            raise RemoteVoiceStudioConfigurationError(
                "VoiceStudio Remote rejects localhost and loopback URLs; use a remote HTTPS/Tailscale/cloud endpoint."
            )
        return self.base_url.rstrip("/") + "/"

    def _headers(self, *, json_body: bool = False) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if json_body:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, path: str, *, data: bytes | None = None):
        base_url = self._validated_base_url()
        request = Request(
            urljoin(base_url, path.lstrip("/")),
            data=data,
            headers=self._headers(json_body=data is not None),
            method="POST" if data is not None else "GET",
        )
        return self._opener(request, timeout=self.timeout_seconds)

    def _json(self, path: str) -> dict[str, Any]:
        with self._request(path) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {"items": payload}

    @staticmethod
    def _error_detail(exc: HTTPError) -> str:
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except OSError:
            detail = ""
        return f": {detail[:400]}" if detail else ""

    def is_available(self) -> bool:
        return bool(self.health_check().get("available"))

    def health_check(self) -> dict[str, Any]:
        try:
            payload = self._json("health")
            return {
                "available": True,
                "provider": self.provider_id,
                "base_url": self._validated_base_url().rstrip("/"),
                "status": payload.get("status", "ready"),
                "version": payload.get("version"),
                "auth_configured": bool(self.api_key),
                "remote_only": True,
            }
        except RemoteVoiceStudioConfigurationError as exc:
            return {
                "available": False,
                "provider": self.provider_id,
                "status": "remote_url_required_or_rejected",
                "detail": str(exc),
                "remote_only": True,
            }
        except HTTPError as exc:
            return {
                "available": False,
                "provider": self.provider_id,
                "status": "remote_auth_required" if exc.code == 401 else "remote_http_error",
                "detail": f"HTTP {exc.code}{self._error_detail(exc)}",
                "remote_only": True,
            }
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            return {
                "available": False,
                "provider": self.provider_id,
                "status": "remote_unreachable",
                "detail": str(exc),
                "remote_only": True,
            }

    def capabilities(self) -> dict[str, Any]:
        return {
            "synthesis": True,
            "remote_only": True,
            "multilingual": True,
            "voice_clone": True,
            "voice_clone_method": "saved_voice_profile",
            "voice_design": True,
            "voice_design_scope": "engine_dependent",
            # The API exposes a free-form description, but does not advertise
            # per-engine gender/age/pitch capability. Do not show false controls.
            "gender": False,
            "age": False,
            "pitch": False,
            "reference_audio": False,
            "reference_audio_note": "Use a voice profile created on the remote VoiceStudio service.",
            "speed": True,
            "speed_range": {"min": 0.85, "max": 1.20, "step": 0.01},
            "remote_api_speed_range": {"min": 0.25, "max": 4.0},
            "engine_discovery": True,
            # A remote engine catalogue does not advertise design controls per
            # engine. Keep its free-form design extension callable, but do not
            # expose a generic UI mode that would promise unsupported controls.
            "modes": ["auto", "voice_clone"],
        }

    def _catalog(self) -> dict[str, Any]:
        return self._json("v1/audio/voices")

    def list_voices(self) -> list[dict[str, Any]]:
        try:
            voices = self._catalog().get("voices", [])
            return [voice for voice in voices if isinstance(voice, dict)]
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, RemoteVoiceStudioConfigurationError):
            return []

    def list_engines(self) -> list[dict[str, Any]]:
        """Discover engine IDs from the remote runtime; never mirror README lists."""

        try:
            engines = self._catalog().get("engines", [])
            if isinstance(engines, dict):
                return [
                    dict(value, engine_id=key) if isinstance(value, dict) else {"engine_id": key, "value": value}
                    for key, value in engines.items()
                ]
            return [item if isinstance(item, dict) else {"engine_id": str(item)} for item in engines]
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, RemoteVoiceStudioConfigurationError):
            return []

    def test_connection(self) -> dict[str, Any]:
        """Check both health and authenticated discovery without generating audio."""

        health = self.health_check()
        if not health.get("available"):
            return health
        try:
            catalog = self._catalog()
        except HTTPError as exc:
            return {
                **health,
                "available": False,
                "status": "remote_auth_required" if exc.code == 401 else "remote_http_error",
                "detail": f"HTTP {exc.code}{self._error_detail(exc)}",
            }
        except (URLError, TimeoutError, OSError, ValueError, RemoteVoiceStudioConfigurationError) as exc:
            return {**health, "available": False, "status": "remote_unreachable", "detail": str(exc)}
        return {
            **health,
            "status": "ready",
            "voices": len(catalog.get("voices", [])),
            "engines": len(catalog.get("engines", [])),
        }

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
        if request.ref_audio:
            raise ValueError(
                "VoiceStudio Remote accepts a saved remote voice profile ID, not a local reference-audio upload."
            )
        payload: dict[str, Any] = {
            "model": str(options.get("engine") or options.get("model") or "tts-1"),
            "input": request.text,
            "voice": request.voice_id or "default",
            "response_format": "wav",
            "speed": float(options.get("speed", 1.0)),
            "language": request.language.split("-", 1)[0],
        }
        if options.get("mode") == "voice_design":
            description = self._design_description(options)
            if description:
                payload["description"] = description
        for key in (
            "instruct", "duration", "seed", "denoise", "preprocess_prompt", "chunk_duration",
            "chunk_threshold", "num_step", "guidance_scale",
        ):
            if key in options:
                payload[key] = options[key]
        output = Path(request.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        started = perf_counter()
        try:
            with self._request("v1/audio/speech", data=json.dumps(payload, ensure_ascii=False).encode("utf-8")) as response:
                first_response_at = perf_counter()
                audio = response.read()
                completed_at = perf_counter()
                headers = getattr(response, "headers", {})
                synthesis_header = headers.get("X-VoiceStudio-Synthesis-Seconds") or headers.get("X-Process-Time")
        except HTTPError as exc:
            retry = " (retry after the server's Retry-After interval)" if exc.code in (429, 503) else ""
            raise RuntimeError(f"VoiceStudio Remote synthesis failed: HTTP {exc.code}{retry}{self._error_detail(exc)}") from exc
        except RemoteVoiceStudioConfigurationError:
            raise
        except (URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"VoiceStudio Remote is unreachable: {exc}") from exc
        if not audio:
            raise RuntimeError("VoiceStudio Remote returned an empty audio response.")
        output.write_bytes(audio)
        duration, sample_rate = wav_metadata(output)
        try:
            remote_synthesis_seconds = float(synthesis_header) if synthesis_header is not None else None
        except (TypeError, ValueError):
            remote_synthesis_seconds = None
        self.last_metrics = {
            "request_latency_seconds": round(first_response_at - started, 3),
            "download_seconds": round(completed_at - first_response_at, 3),
            "end_to_end_seconds": round(completed_at - started, 3),
            "remote_synthesis_seconds": remote_synthesis_seconds,
            "audio_duration_seconds": duration,
            "output_bytes": len(audio),
        }
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
