#!/usr/bin/env python3
"""Provider-neutral synthesis, preview, cache, and scene job states."""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable

from src.providers.base import VoiceGenerationRequest, VoiceSynthesisResult
from src.providers.voice.registry import DEFAULT_VOICE_PROVIDER, ProviderRegistry

DEFAULT_PREVIEW_TEXT = (
    "Xin chào, đây là bản nghe thử giọng đọc tiếng Việt. "
    "Giọng nói này sẽ được dùng để kể câu chuyện rõ ràng, tự nhiên và dễ theo dõi "
    "trong các cảnh của video. Bạn có thể nghe nhịp đọc, âm sắc và cách phát âm trước khi tạo toàn bộ lời kể."
)

DEFAULT_VOICE_MODE = "voice_design"
DEFAULT_OMNIVOICE_DESIGN = {"gender": "male", "pitch": "moderate"}


def _speed_to_rate(speed: float) -> str:
    percent = round((speed - 1.0) * 100)
    return f"{percent:+d}%"


@dataclass
class VoiceConfig:
    provider: str = DEFAULT_VOICE_PROVIDER
    mode: str = DEFAULT_VOICE_MODE
    voice_id: str | None = None
    language: str = "vi"
    speed: float = 1.10
    design: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_OMNIVOICE_DESIGN))
    reference_audio: Path | str | None = None
    selected_preview: str | None = None
    approval_required: bool = False
    approved: bool = False
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_project(cls, project_data: dict[str, Any]) -> "VoiceConfig":
        voice = project_data.get("voice")
        if isinstance(voice, dict):
            known = {
                "provider", "mode", "voice_id", "language", "speed", "engine", "base_url", "timeout_seconds",
                "api_key", "design", "reference_audio",
                "selected_preview", "approval_required", "approved",
            }
            design = dict(DEFAULT_OMNIVOICE_DESIGN)
            design.update(dict(voice.get("design") or {}))
            return cls(
                provider=str(voice.get("provider") or DEFAULT_VOICE_PROVIDER),
                mode=str(voice.get("mode") or DEFAULT_VOICE_MODE),
                voice_id=str(voice["voice_id"]) if voice.get("voice_id") else None,
                language=str(voice.get("language") or project_data.get("language") or "vi"),
                speed=float(voice.get("speed", 1.10)),
                design=design,
                reference_audio=voice.get("reference_audio"),
                selected_preview=str(voice["selected_preview"]) if voice.get("selected_preview") else None,
                approval_required=bool(voice.get("approval_required", False)),
                approved=bool(voice.get("approved", False)),
                options={key: value for key, value in voice.items() if key not in known},
            )
        # Backward-compatible normalization for existing narration.json files.
        legacy_rate = str(project_data.get("rate", "+0%"))
        try:
            speed = 1.0 + float(legacy_rate.rstrip("%")) / 100.0
        except ValueError:
            speed = 1.0
        return cls(
            provider=DEFAULT_VOICE_PROVIDER,
            voice_id=str(voice or project_data.get("default_voice") or "default"),
            language=str(project_data.get("language") or "vi"),
            speed=speed,
            mode=DEFAULT_VOICE_MODE,
            design=dict(DEFAULT_OMNIVOICE_DESIGN),
            options={"rate": legacy_rate},
        )

    def provider_options(self) -> dict[str, Any]:
        result = self.safe_options()
        result.update({"mode": self.mode, "speed": self.speed, "design": self.design})
        return result

    def safe_options(self) -> dict[str, Any]:
        secret_names = {"api_key", "authorization", "remote_api_key", "voicestudio_api_key"}
        return {key: value for key, value in self.options.items() if key.lower() not in secret_names}

    def to_dict(self) -> dict[str, Any]:
        result = {
            "provider": self.provider,
            "mode": self.mode,
            "language": self.language,
            "voice_id": self.voice_id,
            "design": dict(self.design),
            "speed": self.speed,
            "reference_audio": str(self.reference_audio) if self.reference_audio else None,
            "selected_preview": self.selected_preview,
            "approval_required": self.approval_required,
            "approved": self.approved,
        }
        result.update(self.safe_options())
        return result


class VoiceJobStatus(str, Enum):
    QUEUED = "queued"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class VoiceBatchItem:
    scene_id: str
    text: str
    output_path: Path | str


class VoiceService:
    def __init__(
        self,
        project_root: Path | str,
        *,
        registry: ProviderRegistry | None = None,
        fallback: bool = True,
    ):
        self.project_root = Path(project_root).resolve()
        self.cache_root = self.project_root / ".voice-cache"
        self.preview_root = self.project_root / ".voice-preview"
        self.registry = registry or ProviderRegistry()
        self.fallback = fallback
        self.last_warning: str | None = None
        self.last_metrics: dict[str, Any] | None = None
        self._resolutions: dict[str, Any] = {}

    def _reference_path(self, reference_audio: Path | str | None) -> Path | None:
        if not reference_audio:
            return None
        path = Path(reference_audio)
        return path if path.is_absolute() else self.project_root / path

    def _reference_hash(self, reference_audio: Path | str | None) -> str | None:
        path = self._reference_path(reference_audio)
        if path is None:
            return None
        if not path.is_file():
            return "missing"
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def cache_key(self, text: str, config: VoiceConfig, *, selected_provider: str | None = None) -> str:
        design = config.design
        payload = {
            "provider": selected_provider or config.provider,
            "engine": config.options.get("engine") or config.options.get("model"),
            "voice_id": config.voice_id,
            "language": config.language,
            "mode": config.mode,
            "design": design,
            "gender": design.get("gender"),
            "age": design.get("age"),
            "pitch": design.get("pitch") or config.options.get("pitch"),
            "speed": config.speed,
            "text": text,
            "reference_audio_hash": self._reference_hash(config.reference_audio),
            "options": config.safe_options(),
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def synthesize(self, text: str, config: VoiceConfig, output_path: Path | str) -> VoiceSynthesisResult:
        if config.provider not in self._resolutions:
            self._resolutions[config.provider] = self.registry.resolve(config.provider, fallback=self.fallback)
        resolution = self._resolutions[config.provider]
        self.last_warning = resolution.warning
        key = self.cache_key(text, config, selected_provider=resolution.selected_provider)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        cached_audio = self.cache_root / f"{key}.wav"
        cached_metadata = self.cache_root / f"{key}.json"
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        if cached_audio.is_file() and cached_metadata.is_file():
            if output.resolve() != cached_audio.resolve():
                shutil.copy2(cached_audio, output)
            metadata = json.loads(cached_metadata.read_text(encoding="utf-8"))
            metadata.update({"audio_file": output, "cache_hit": True})
            self.last_metrics = {"cache_hit": True}
            return VoiceSynthesisResult(**metadata)

        temp_audio = self.cache_root / f"{key}.generating.wav"
        rate = str(config.options.get("rate") or _speed_to_rate(config.speed))
        pitch = str(config.options.get("pitch") or "+0Hz")
        request = VoiceGenerationRequest(
            text=text,
            voice_id=config.voice_id or "default",
            language=config.language,
            rate=rate,
            pitch=pitch,
            output_path=temp_audio,
            ref_audio=self._reference_path(config.reference_audio),
            options=config.provider_options(),
        )
        result = resolution.provider.synthesize(request)
        self.last_metrics = getattr(resolution.provider, "last_metrics", None)
        generated = Path(result.audio_file)
        generated.replace(cached_audio)
        result.audio_file = output
        result.provider = resolution.selected_provider
        result.language = config.language
        result.cache_hit = False
        if output.resolve() != cached_audio.resolve():
            shutil.copy2(cached_audio, output)
        metadata = result.to_dict()
        metadata["audio_file"] = str(cached_audio)
        metadata["cache_hit"] = False
        cached_metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result

    def generate_voice_preview(
        self,
        config: VoiceConfig,
        sample_text: str = DEFAULT_PREVIEW_TEXT,
        output_path: Path | str | None = None,
    ) -> VoiceSynthesisResult:
        key = self.cache_key(sample_text, config)[:12]
        output = Path(output_path) if output_path else self.preview_root / f"{config.provider}-{key}.wav"
        return self.synthesize(sample_text, config, output)

    def synthesize_batch(
        self,
        items: Iterable[VoiceBatchItem],
        config: VoiceConfig,
        on_status: Callable[[str, VoiceJobStatus, str | None], None] | None = None,
    ) -> list[dict[str, Any]]:
        jobs = list(items)
        for item in jobs:
            if on_status:
                on_status(item.scene_id, VoiceJobStatus.QUEUED, None)
        results: list[dict[str, Any]] = []
        for item in jobs:
            if on_status:
                on_status(item.scene_id, VoiceJobStatus.GENERATING, None)
            try:
                result = self.synthesize(item.text, config, item.output_path)
                results.append({"scene_id": item.scene_id, "status": VoiceJobStatus.COMPLETE.value, "result": result.to_dict()})
                if on_status:
                    on_status(item.scene_id, VoiceJobStatus.COMPLETE, None)
            except Exception as exc:
                results.append({"scene_id": item.scene_id, "status": VoiceJobStatus.FAILED.value, "error": str(exc)})
                if on_status:
                    on_status(item.scene_id, VoiceJobStatus.FAILED, str(exc))
        return results
