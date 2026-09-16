#!/usr/bin/env python3
"""Voice selection state/actions used by CLI now and a desktop UI later."""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.providers.voice.registry import ProviderRegistry
from src.services.voice_service import VoiceConfig, VoiceService

VOICE_PREVIEW_TEXT = (
    "Đại Tây Dương không chỉ là một khoảng nước nằm giữa các lục địa. "
    "Nó là một hệ thống khổng lồ kết nối khí hậu, địa chất, thương mại và lịch sử của cả thế giới."
)
SPEED_PRESETS = {"slow": 0.95, "normal": 1.00, "natural_plus": 1.08, "fast": 1.12, "fast_plus": 1.15}
VALID_MODES = {"auto", "voice_design", "voice_clone"}
VALID_GENDERS = {"male", "female"}
VALID_AGES = {"young adult", "middle-aged", "older adult"}
VALID_PITCHES = {"low", "moderate", "high"}


class VoiceControlError(ValueError):
    pass


@dataclass
class VoiceControlState:
    voiceProvider: str = "omnivoice"
    voiceMode: str = "auto"
    gender: str = "male"
    age: str = "young adult"
    pitch: str = "moderate"
    speed: float = 1.10
    engine: str | None = None
    voiceId: str | None = None
    referenceAudio: str | None = None
    remoteBaseUrl: str | None = None
    remoteStatus: str = "disconnected"
    previewText: str = VOICE_PREVIEW_TEXT
    previewStatus: str = "idle"
    previewFile: str | None = None
    selectedPreview: str | None = None


class VoiceControlService:
    def __init__(self, project_root: Path | str, *, registry: ProviderRegistry | None = None):
        self.project_root = Path(project_root).resolve()
        self.narration_path = self.project_root / "narration.json"
        self.state_path = self.project_root / "voice-control-state.json"
        self.preview_root = self.project_root / "output" / "voice_previews"
        self.registry = registry or ProviderRegistry()
        if not self.narration_path.is_file():
            raise FileNotFoundError(f"Narration source not found: {self.narration_path}")
        self.state = self._load_state()

    def _project_data(self) -> dict[str, Any]:
        return json.loads(self.narration_path.read_text(encoding="utf-8"))

    def _load_state(self) -> VoiceControlState:
        if self.state_path.is_file():
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            allowed = VoiceControlState.__dataclass_fields__
            return VoiceControlState(**{key: value for key, value in raw.items() if key in allowed})
        config = VoiceConfig.from_project(self._project_data())
        design = config.design
        return VoiceControlState(
            voiceProvider=config.provider,
            voiceMode=config.mode,
            gender=str(design.get("gender") or "male"),
            age=str(design.get("age") or "young adult"),
            pitch=str(design.get("pitch") or "moderate"),
            speed=config.speed if config.selected_preview else 1.10,
            engine=config.engine,
            voiceId=config.voice_id,
            referenceAudio=str(config.reference_audio) if config.reference_audio else None,
            remoteBaseUrl=config.base_url,
            selectedPreview=config.selected_preview,
        )

    def _save_state(self) -> dict[str, Any]:
        payload = asdict(self.state)
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload

    def _provider(self, config: VoiceConfig, *, require_available: bool = True):
        try:
            provider = self.registry.resolve(
                config.provider,
                fallback=False,
                configuration=config.provider_configuration(),
                require_available=False,
            ).provider
        except (KeyError, RuntimeError) as exc:
            raise VoiceControlError(str(exc)) from exc
        if require_available and not provider.is_available():
            health = provider.health_check()
            detail = health.get("detail")
            suffix = f" {detail}" if detail else ""
            raise VoiceControlError(f"Voice provider '{config.provider}' is not available.{suffix}")
        return provider

    def validate(self, config: VoiceConfig, *, require_available: bool = True) -> dict[str, Any]:
        provider = self._provider(config, require_available=require_available)
        capabilities = provider.capabilities()
        if config.mode not in VALID_MODES:
            raise VoiceControlError(f"Unsupported voice mode: {config.mode}")
        if config.mode not in capabilities.get("modes", ["auto"]):
            raise VoiceControlError(f"Provider '{config.provider}' does not support mode '{config.mode}'.")
        speed_range = capabilities.get("speed_range") or {"min": 0.85, "max": 1.20}
        if not float(speed_range["min"]) <= config.speed <= float(speed_range["max"]):
            raise VoiceControlError(
                f"Speed {config.speed:.2f} is invalid; use {speed_range['min']:.2f}–{speed_range['max']:.2f}."
            )
        if not config.language.strip():
            raise VoiceControlError("Language is required.")
        supported_languages = capabilities.get("supported_languages")
        if supported_languages and config.language.split("-", 1)[0] not in supported_languages:
            raise VoiceControlError(f"Language '{config.language}' is not supported by '{config.provider}'.")
        if config.mode == "voice_design":
            gender = config.design.get("gender")
            age = config.design.get("age")
            pitch = config.design.get("pitch")
            if gender not in VALID_GENDERS:
                raise VoiceControlError("Voice design requires gender 'male' or 'female'.")
            if not capabilities.get("gender"):
                raise VoiceControlError(f"Provider '{config.provider}' does not support gender design.")
            if age is not None and (age not in VALID_AGES or not capabilities.get("age")):
                raise VoiceControlError(f"Provider '{config.provider}' does not support age design.")
            if pitch not in VALID_PITCHES:
                raise VoiceControlError("Pitch must be low, moderate, or high.")
            if not capabilities.get("pitch"):
                raise VoiceControlError(f"Provider '{config.provider}' does not support pitch design.")
        if config.mode == "voice_clone":
            if not capabilities.get("voice_clone"):
                raise VoiceControlError(f"Provider '{config.provider}' does not support voice cloning.")
            if capabilities.get("voice_clone_method") == "saved_voice_profile":
                if not config.voice_id:
                    raise VoiceControlError("VoiceStudio clone mode requires a saved voice profile.")
            else:
                reference = self._reference_path(config.reference_audio)
                if reference is None or not reference.is_file():
                    raise VoiceControlError("Voice clone mode requires an existing reference audio file.")
        if config.voice_id:
            voices = provider.list_voices()
            known_ids = {str(item.get("voice_id")) for item in voices}
            if known_ids and config.voice_id not in known_ids:
                raise VoiceControlError(f"Voice ID '{config.voice_id}' was not reported by '{config.provider}'.")
        return capabilities

    def _reference_path(self, value: Path | str | None) -> Path | None:
        if not value:
            return None
        path = Path(value)
        return path if path.is_absolute() else self.project_root / path

    def config_from_state(self, *, api_key: str | None = None) -> VoiceConfig:
        provider = self.registry.get(self.state.voiceProvider)
        capabilities = provider.capabilities()
        design: dict[str, Any] = {}
        if self.state.voiceMode == "voice_design":
            if capabilities.get("gender"):
                design["gender"] = self.state.gender
            if capabilities.get("age"):
                design["age"] = self.state.age
            if capabilities.get("pitch"):
                design["pitch"] = self.state.pitch
        return VoiceConfig(
            provider=self.state.voiceProvider,
            mode=self.state.voiceMode,
            voice_id=self.state.voiceId,
            language="vi",
            speed=self.state.speed,
            engine=self.state.engine,
            design=design,
            reference_audio=self.state.referenceAudio,
            base_url=self.state.remoteBaseUrl,
            api_key=api_key,
            approval_required=True,
            approved=False,
        )

    def ui_contract(self) -> dict[str, Any]:
        providers = self.registry.catalog()
        if self.state.voiceProvider == "voicestudio_remote":
            config = self.config_from_state()
            provider = self._provider(config, require_available=False)
            health = provider.health_check()
            for item in providers:
                if item["provider_id"] == "voicestudio_remote":
                    item.update({
                        "available": health.get("available"),
                        "status": health.get("status", "remote_unreachable"),
                        "capabilities": provider.capabilities(),
                        "voices": provider.list_voices() if health.get("available") else [],
                        "engines": provider.list_engines() if health.get("available") else [],
                    })
                    break
        active = next((item for item in providers if item["provider_id"] == self.state.voiceProvider), providers[0])
        caps = active["capabilities"]
        mode = self.state.voiceMode
        return {
            "state": asdict(self.state),
            "providers": providers,
            "profiles": self.list_profiles(),
            "controls": {
                "mode": {"options": caps.get("modes", ["auto"]), "visible": True},
                "gender": {"options": sorted(VALID_GENDERS), "visible": mode == "voice_design" and bool(caps.get("gender"))},
                "age": {"options": sorted(VALID_AGES), "visible": mode == "voice_design" and bool(caps.get("age"))},
                "pitch": {"options": ["low", "moderate", "high"], "visible": mode == "voice_design" and bool(caps.get("pitch"))},
                "speed": {"range": caps.get("speed_range", {"min": 0.85, "max": 1.20, "step": 0.01}), "presets": SPEED_PRESETS},
                "engine": {"options": active.get("engines", []), "visible": bool(caps.get("engine_discovery"))},
                "voiceProfile": {"options": active.get("voices", []), "visible": bool(active.get("voices"))},
                "referenceAudio": {"visible": mode == "voice_clone" and bool(caps.get("reference_audio"))},
                "remoteConnection": {
                    "visible": self.state.voiceProvider == "voicestudio_remote",
                    "baseUrl": self.state.remoteBaseUrl,
                    "status": self.state.remoteStatus,
                    "apiKeyStorage": "transient_form_or_VOICESTUDIO_API_KEY",
                },
            },
            "actions": [
                "setVoiceProvider", "setVoiceMode", "setGender", "setAge", "setPitch", "setSpeed", "setEngine",
                "setRemoteServer", "testRemoteConnection",
                "chooseReferenceAudio", "generatePreview", "playPreview", "selectPreview", "approveVoice",
                "regenerateNarration",
            ],
        }

    def list_profiles(self) -> list[dict[str, Any]]:
        repo_root = self.project_root.parents[1]
        path = repo_root / "config" / "voice_profiles.json"
        if not path.is_file():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [item for item in payload.get("profiles", []) if isinstance(item, dict)]

    def update_state(self, **changes: Any) -> dict[str, Any]:
        aliases = {
            "provider": "voiceProvider", "mode": "voiceMode", "voice_id": "voiceId",
            "reference_audio": "referenceAudio", "preview_text": "previewText", "engine": "engine",
            "remote_base_url": "remoteBaseUrl",
        }
        previous = VoiceControlState(**asdict(self.state))
        try:
            for key, value in changes.items():
                field_name = aliases.get(key, key)
                if field_name not in VoiceControlState.__dataclass_fields__:
                    raise VoiceControlError(f"Unknown voice state field: {key}")
                setattr(self.state, field_name, value)
            config = self.config_from_state()
            self.validate(config, require_available=config.provider != "voicestudio_remote")
        except Exception:
            self.state = previous
            raise
        return self._save_state()

    def choose_reference_audio(self, source: Path | str) -> str:
        source_path = Path(source).resolve()
        if not source_path.is_file():
            raise VoiceControlError(f"Reference audio not found: {source_path}")
        target_root = self.project_root / "references" / "voice"
        target_root.mkdir(parents=True, exist_ok=True)
        target = target_root / source_path.name
        if source_path != target.resolve():
            shutil.copy2(source_path, target)
        self.state.referenceAudio = target.relative_to(self.project_root).as_posix()
        self._save_state()
        return self.state.referenceAudio

    def test_remote_connection(self, base_url: str | None, api_key: str | None = None) -> dict[str, Any]:
        self.update_state(provider="voicestudio_remote", mode="auto", remote_base_url=base_url or None)
        config = self.config_from_state(api_key=api_key or None)
        provider = self._provider(config, require_available=False)
        test_connection = getattr(provider, "test_connection", None)
        if not callable(test_connection):
            raise VoiceControlError("Selected provider does not implement remote connection testing.")
        report = test_connection()
        self.state.remoteStatus = str(report.get("status") or "error")
        self._save_state()
        return report

    def generate_preview(self, *, output_path: Path | str | None = None, api_key: str | None = None):
        config = self.config_from_state(api_key=api_key or None)
        self.validate(config)
        self.state.previewStatus = "generating"
        self._save_state()
        try:
            result = VoiceService(self.project_root, registry=self.registry, fallback=False).generate_voice_preview(
                config, self.state.previewText, output_path,
            )
        except Exception:
            self.state.previewStatus = "failed"
            self._save_state()
            raise
        self.state.previewStatus = "complete"
        if config.provider == "voicestudio_remote":
            self.state.remoteStatus = "ready"
        self.state.previewFile = str(result.audio_file)
        self._save_state()
        return result

    def generate_comparison_previews(self) -> dict[str, Any]:
        self.preview_root.mkdir(parents=True, exist_ok=True)
        voice_service = VoiceService(self.project_root, registry=self.registry, fallback=False)
        previews: list[dict[str, Any]] = []
        for gender in ("male", "female"):
            for speed in (1.08, 1.12):
                preview_id = f"{gender}_{speed:.2f}"
                config = VoiceConfig(
                    provider="omnivoice",
                    mode="voice_design",
                    voice_id=None,
                    language="vi",
                    design={"gender": gender, "pitch": "moderate"},
                    speed=speed,
                    approval_required=True,
                    approved=False,
                )
                self.validate(config)
                output = self.preview_root / f"{preview_id}.wav"
                result = voice_service.generate_voice_preview(config, VOICE_PREVIEW_TEXT, output)
                selected_config = config.to_dict()
                selected_config["voice_id"] = result.voice_id
                previews.append({
                    "preview_id": preview_id,
                    "file": str(output),
                    "duration": result.duration,
                    "sample_rate": result.sample_rate,
                    "cache_hit": result.cache_hit,
                    "age_control_applied": False,
                    "config": selected_config,
                })
        report = {
            "status": "awaiting_selection",
            "preview_text": VOICE_PREVIEW_TEXT,
            "previews": previews,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        (self.preview_root / "manifest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self.state.previewStatus = "complete"
        self._save_state()
        return report

    def select_preview(self, preview_id: str) -> dict[str, Any]:
        manifest_path = self.preview_root / "manifest.json"
        if not manifest_path.is_file():
            raise VoiceControlError("Generate comparison previews before selecting one.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        preview = next((item for item in manifest.get("previews", []) if item.get("preview_id") == preview_id), None)
        if preview is None:
            raise VoiceControlError(f"Unknown voice preview: {preview_id}")
        config = VoiceConfig.from_project({"voice": preview["config"]})
        config.selected_preview = preview_id
        config.approval_required = True
        config.approved = False
        project = self._project_data()
        project["voice"] = config.to_dict()
        self.narration_path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.state.voiceProvider = config.provider
        self.state.voiceMode = config.mode
        self.state.gender = str(config.design.get("gender") or "male")
        self.state.pitch = str(config.design.get("pitch") or "moderate")
        self.state.speed = config.speed
        self.state.voiceId = config.voice_id
        self.state.previewFile = preview["file"]
        self.state.selectedPreview = preview_id
        self._save_state()
        return project["voice"]

    def approve_voice(self) -> dict[str, Any]:
        project = self._project_data()
        config = VoiceConfig.from_project(project)
        if not config.selected_preview:
            raise VoiceControlError("Select a preview before approving voice narration.")
        self.validate(config)
        config.approval_required = True
        config.approved = True
        project["voice"] = config.to_dict()
        self.narration_path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return project["voice"]

    def regenerate_narration(self) -> dict[str, Any]:
        config = VoiceConfig.from_project(self._project_data())
        if not config.approved:
            raise VoiceControlError("Approve the selected voice before regenerating narration.")
        from src.services.narration_timeline import NarrationTimelineService

        repo_root = self.project_root.parents[1]
        return NarrationTimelineService(repo_root, self.project_root.name).prepare(synthesize=True)
