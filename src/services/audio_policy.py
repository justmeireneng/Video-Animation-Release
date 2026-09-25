from __future__ import annotations

from typing import Any


class AudioPolicyService:
    MODES = {"mute", "background", "full"}

    @classmethod
    def defaults(cls, has_audio: bool, settings: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = settings or {}
        requested_mode = str(settings.get("mode", "background"))
        mode = requested_mode if requested_mode in cls.MODES else "background"
        if not has_audio:
            mode = "mute"
        volume = float(settings.get("volume", 0.30)) if has_audio else 0.0
        return {
            "mode": mode,
            "enabled": bool(has_audio and mode != "mute"),
            "volume": max(0.0, min(1.0, volume)),
            "duck_under_narration": bool(settings.get("duck_under_narration", True)),
            "fade_in": max(0.0, float(settings.get("fade_in", 0.15))),
            "fade_out": max(0.0, float(settings.get("fade_out", 0.20))),
        }

    @classmethod
    def update(cls, current: dict[str, Any], *, mode: str, volume: float | None = None,
               duck: bool | None = None, fade_in: float | None = None,
               fade_out: float | None = None) -> dict[str, Any]:
        if mode not in cls.MODES:
            raise ValueError(f"Audio mode must be one of {sorted(cls.MODES)}.")
        updated = dict(current)
        updated["mode"] = mode
        updated["enabled"] = mode != "mute"
        if volume is not None:
            if not 0 <= volume <= 1:
                raise ValueError("Source audio volume must be in the 0..1 range.")
            updated["volume"] = volume
        if duck is not None:
            updated["duck_under_narration"] = duck
        if fade_in is not None:
            updated["fade_in"] = max(0.0, fade_in)
        if fade_out is not None:
            updated["fade_out"] = max(0.0, fade_out)
        return updated
