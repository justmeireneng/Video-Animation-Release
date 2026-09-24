#!/usr/bin/env python3
"""Voice selection state/actions used by CLI now and a desktop UI later."""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.providers.voice.registry import DEFAULT_VOICE_PROVIDER, ProviderRegistry
from src.services.voice_service import DEFAULT_VOICE_MODE, VoiceConfig, VoiceService

VOICE_PREVIEW_TEXT = (
    "Đại Tây Dương không chỉ là một khoảng nước nằm giữa các lục địa. "
    "Nó là một hệ thống khổng lồ kết nối khí hậu, địa chất, thương mại và lịch sử của cả thế giới."
)
SPEED_PRESETS = {
    "slow": 0.95,
    "normal": 1.00,
    "natural_plus": 1.08,
    "default": 1.10,
    "fast": 1.12,
    "fast_plus": 1.15,
}
VALID_MODES = {"auto", "voice_design", "voice_clone"}
VALID_GENDERS = {"male", "female"}
VALID_AGES = {"young adult", "middle-aged", "older adult"}
VALID_PITCHES = {"low", "moderate", "high"}


class VoiceControlError(ValueError):
    pass


@dataclass
class VoiceControlState:
    voiceProvider: str = DEFAULT_VOICE_PROVIDER
    voiceMode: str = DEFAULT_VOICE_MODE
    gender: str = "male"
    age: str = "young adult"
    pitch: str = "low"
    speed: float = 1.10
    voiceId: str | None = None
    referenceAudio: str | None = None
    previewText: str = VOICE_PREVIEW_TEXT
    previewStatus: str = "idle"
    previewFile: str | None = None
    selectedPreview: str | None = None


class VoiceControlService:
    def __init__(self, project_root: Path | str, *, registry: ProviderRegistry | None = None):
        self.project_root = Path(project_root).resolve()
        self.narration_path = self.project_root / "narration.json"
        self.manifest_path = self.project_root / "project.json"
        self.state_path = self.project_root / "voice-control-state.json"
        self.preview_root = self.project_root / ("voice/previews" if self.manifest_path.is_file() else "output/voice_previews")
        self.registry = registry or ProviderRegistry()
        if not self.narration_path.is_file() and not self.manifest_path.is_file():
            raise FileNotFoundError(f"Project voice config not found in: {self.project_root}")
        self.state = self._load_state()

    def _project_data(self) -> dict[str, Any]:
        path = self.manifest_path if self.manifest_path.is_file() else self.narration_path
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_project_data(self, project: dict[str, Any]) -> None:
        path = self.manifest_path if self.manifest_path.is_file() else self.narration_path
        path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _load_state(self) -> VoiceControlState:
        if self.state_path.is_file():
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            allowed = VoiceControlState.__dataclass_fields__
            return self._normalize_state(VoiceControlState(**{key: value for key, value in raw.items() if key in allowed}))
        config = VoiceConfig.from_project(self._project_data())
        design = config.design
        return self._normalize_state(VoiceControlState(
            voiceProvider=config.provider,
            voiceMode=config.mode,
            gender=str(design.get("gender") or "male"),
            age=str(design.get("age") or "young adult"),
            pitch=str(design.get("pitch") or "low"),
            speed=config.speed if config.selected_preview else 1.10,
            voiceId=config.voice_id,
            referenceAudio=str(config.reference_audio) if config.reference_audio else None,
            selectedPreview=config.selected_preview,
        ))

    def _normalize_state(self, state: VoiceControlState) -> VoiceControlState:
        """Migrate a saved panel state to the only production voice engine."""

        state.voiceProvider = DEFAULT_VOICE_PROVIDER
        capabilities = self.registry.get(DEFAULT_VOICE_PROVIDER).capabilities()
        supported_modes = capabilities.get("modes", ["auto"])
        if state.voiceMode not in supported_modes:
            state.voiceMode = DEFAULT_VOICE_MODE if DEFAULT_VOICE_MODE in supported_modes else supported_modes[0]
        speed_range = capabilities.get("speed_range", {"min": 0.85, "max": 1.20})
        state.speed = min(max(float(state.speed), float(speed_range["min"])), float(speed_range["max"]))
        return state

    def _save_state(self) -> dict[str, Any]:
        payload = asdict(self.state)
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload

    def _provider(self, config: VoiceConfig, *, require_available: bool = True):
        try:
            provider = self.registry.resolve(config.provider, fallback=False).provider
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
                    raise VoiceControlError("Voice clone mode requires a saved voice profile.")
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

    def config_from_state(self) -> VoiceConfig:
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
            design=design,
            reference_audio=self.state.referenceAudio,
            approval_required=True,
            approved=False,
        )

    def ui_contract(self) -> dict[str, Any]:
        providers = self.registry.catalog()
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
                "voiceProfile": {"options": active.get("voices", []), "visible": bool(active.get("voices"))},
                "referenceAudio": {"visible": mode == "voice_clone" and bool(caps.get("reference_audio"))},
            },
            "actions": [
                "setVoiceMode", "setGender", "setAge", "setPitch", "setSpeed",
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
        return [
            item for item in payload.get("profiles", [])
            if isinstance(item, dict) and item.get("provider", DEFAULT_VOICE_PROVIDER) == DEFAULT_VOICE_PROVIDER
        ]

    def update_state(self, **changes: Any) -> dict[str, Any]:
        aliases = {
            "provider": "voiceProvider", "mode": "voiceMode", "voice_id": "voiceId",
            "reference_audio": "referenceAudio", "preview_text": "previewText",
        }
        previous = VoiceControlState(**asdict(self.state))
        try:
            for key, value in changes.items():
                field_name = aliases.get(key, key)
                if field_name not in VoiceControlState.__dataclass_fields__:
                    raise VoiceControlError(f"Unknown voice state field: {key}")
                if field_name == "voiceProvider" and value != DEFAULT_VOICE_PROVIDER:
                    raise VoiceControlError("Only OmniVoice is active in this production build.")
                setattr(self.state, field_name, value)
            config = self.config_from_state()
            self.validate(config)
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

    def generate_preview(self, *, output_path: Path | str | None = None):
        config = self.config_from_state()
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
                    design={"gender": gender, "pitch": "low"},
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
        # Preserve exactly the controls used for this take. Defaults added by
        # newer provider versions must not retroactively invalidate an older
        # preview made by a provider without that control.
        config.design = dict(preview["config"].get("design") or {})
        config.selected_preview = preview_id
        config.approval_required = True
        config.approved = False
        project = self._project_data()
        project["voice"] = config.to_dict()
        self._save_project_data(project)
        self.state.voiceProvider = config.provider
        self.state.voiceMode = config.mode
        self.state.gender = str(config.design.get("gender") or "male")
        self.state.pitch = str(config.design.get("pitch") or "low")
        self.state.speed = config.speed
        self.state.voiceId = config.voice_id
        self.state.previewFile = preview["file"]
        self.state.selectedPreview = preview_id
        self._save_state()
        return project["voice"]

    def approve_voice(self) -> dict[str, Any]:
        project = self._project_data()
        config = VoiceConfig.from_project(project)
        if isinstance(project.get("voice"), dict) and isinstance(project["voice"].get("design"), dict):
            config.design = dict(project["voice"]["design"])
        if not config.selected_preview:
            raise VoiceControlError("Select a preview before approving voice narration.")
        self.validate(config)
        config.approval_required = True
        config.approved = True
        project["voice"] = config.to_dict()
        self._save_project_data(project)
        return project["voice"]

    def regenerate_narration(self) -> dict[str, Any]:
        config = VoiceConfig.from_project(self._project_data())
        if not config.approved:
            raise VoiceControlError("Approve the selected voice before regenerating narration.")
        from src.services.narration_timeline import NarrationTimelineService

        repo_root = self.project_root.parents[1]
        return NarrationTimelineService(repo_root, self.project_root.name).prepare(synthesize=True)
