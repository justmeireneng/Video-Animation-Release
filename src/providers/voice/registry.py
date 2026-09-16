#!/usr/bin/env python3
"""Lazy registry for voice providers that are active in this build."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Callable

from ..base import VoiceProvider

DEFAULT_VOICE_PROVIDER = "omnivoice"


def _lazy(module_name: str, class_name: str) -> Callable[[], VoiceProvider]:
    def factory() -> VoiceProvider:
        return getattr(import_module(module_name), class_name)()
    return factory


@dataclass
class ProviderResolution:
    provider: VoiceProvider
    requested_provider: str
    selected_provider: str
    warning: str | None = None


class ProviderRegistry:
    def __init__(self, factories: dict[str, Callable[[], VoiceProvider]] | None = None):
        self._factories = factories or {
            "omnivoice": _lazy("src.providers.voice.omnivoice", "OmniVoiceProvider"),
        }
        self._active_id: str | None = None
        self._active: VoiceProvider | None = None

    def get(self, provider_id: str) -> VoiceProvider:
        if provider_id not in self._factories:
            raise KeyError(f"Unknown voice provider: {provider_id}")
        if self._active_id != provider_id:
            self.release_active()
            self._active_id = provider_id
            self._active = self._factories[provider_id]()
        return self._active

    def resolve(
        self,
        provider_id: str,
        *,
        fallback: bool = True,
        configuration: dict | None = None,
        require_available: bool = True,
    ) -> ProviderResolution:
        requested = provider_id or DEFAULT_VOICE_PROVIDER
        if requested not in self._factories:
            if not fallback:
                raise KeyError(f"Unknown voice provider: {requested}")
            warning = f"Unknown voice provider '{requested}'; using '{DEFAULT_VOICE_PROVIDER}'."
            return ProviderResolution(self.get(DEFAULT_VOICE_PROVIDER), requested, DEFAULT_VOICE_PROVIDER, warning)
        provider = self.get(requested)
        # Configuration remains part of the abstraction for a future provider,
        # but the production registry intentionally activates OmniVoice only.
        configure = getattr(provider, "configure", None)
        if configuration and callable(configure):
            configure(**configuration)
        if requested != DEFAULT_VOICE_PROVIDER and require_available and not provider.is_available():
            if not fallback:
                raise RuntimeError(f"Voice provider '{requested}' is not available.")
            warning = f"Voice provider '{requested}' is unavailable; using '{DEFAULT_VOICE_PROVIDER}'."
            return ProviderResolution(self.get(DEFAULT_VOICE_PROVIDER), requested, DEFAULT_VOICE_PROVIDER, warning)
        return ProviderResolution(provider, requested, requested)

    def release_active(self) -> None:
        if self._active is not None:
            release = getattr(self._active, "release", None)
            if callable(release):
                release()
        self._active = None
        self._active_id = None

    def catalog(self, *, check_health: bool = True) -> list[dict]:
        items = []
        for provider_id in self._factories:
            provider = self.get(provider_id)
            health = provider.health_check() if check_health else {"available": None, "status": "not_checked"}
            entry = {
                "provider_id": provider.provider_id,
                "display_name": provider.display_name,
                "default": provider_id == DEFAULT_VOICE_PROVIDER,
                "available": health.get("available"),
                "status": health.get("status", "ready" if health.get("available") else "not_installed"),
                "capabilities": provider.capabilities(),
                "voices": provider.list_voices() if health.get("available") else [],
            }
            list_engines = getattr(provider, "list_engines", None)
            entry["engines"] = list_engines() if health.get("available") and callable(list_engines) else []
            items.append(entry)
        self.release_active()
        return items
