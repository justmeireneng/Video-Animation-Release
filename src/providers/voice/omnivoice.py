#!/usr/bin/env python3
"""Local bridge to the real k2-fsa OmniVoice runtime."""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..base import VoiceGenerationRequest, VoiceProvider, VoiceSynthesisResult, wav_metadata

MIN_AVAILABLE_MEMORY_BYTES = 3 * 1024**3


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _available_memory() -> int | None:
    if os.name != "nt":
        return None
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    return int(status.ullAvailPhys) if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None


class OmniVoiceProvider(VoiceProvider):
    provider_id = "omnivoice"
    display_name = "OmniVoice"

    def __init__(self, model_id: str = "k2-fsa/OmniVoice", device: str = "cpu",
                 runtime_python: Path | str | None = None, model_path: Path | str | None = None,
                 runner_path: Path | str | None = None):
        self.model_id = model_id
        self.device = device
        self.repo_root = Path(__file__).resolve().parents[3]
        self.runtime_python = Path(runtime_python) if runtime_python else self._default_runtime()
        self.model_path = Path(model_path) if model_path else self._default_model_path()
        self.runner_path = Path(runner_path) if runner_path else self.repo_root / "scripts" / "omnivoice_infer.py"
        self.last_metrics: dict[str, Any] | None = None

    def _default_runtime(self) -> Path:
        configured = os.environ.get("OMNIVOICE_PYTHON")
        return Path(configured) if configured else self.repo_root / ".venv-omnivoice" / "Scripts" / "python.exe"

    @staticmethod
    def _default_model_path() -> Path:
        configured = os.environ.get("OMNIVOICE_MODEL_PATH")
        if configured:
            return Path(configured)
        snapshots = Path.home() / ".cache" / "huggingface" / "hub" / "models--k2-fsa--OmniVoice" / "snapshots"
        candidates = sorted(snapshots.glob("*"), key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
        complete = [path for path in candidates if (path / "model.safetensors").is_file() and (path / "audio_tokenizer" / "model.safetensors").is_file()]
        return complete[0] if complete else snapshots / "missing"

    def _resource_error(self) -> str | None:
        available = _available_memory()
        if available is not None and available < MIN_AVAILABLE_MEMORY_BYTES and os.environ.get("OMNIVOICE_ALLOW_LOW_MEMORY") != "1":
            return (
                f"OmniVoice needs about 3 GB of free RAM for a safe CPU preview; only {available / 1024**3:.1f} GB is free. "
                "Close memory-heavy apps, then try Generate Preview again."
            )
        return None

    def is_available(self) -> bool:
        return self.runtime_python.is_file() and self.runner_path.is_file() and (self.model_path / "model.safetensors").is_file()

    def health_check(self) -> dict[str, Any]:
        resource_error = self._resource_error()
        return {
            "available": self.is_available(),
            "ready_for_generation": self.is_available() and resource_error is None,
            "status": "ready" if self.is_available() and resource_error is None else "low_memory" if self.is_available() else "not_installed",
            "provider": self.provider_id, "model_id": self.model_id, "model_path": str(self.model_path),
            "device": self.device, "runtime_backend": "omnivoice_local", "detail": resource_error,
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "synthesis": True, "multilingual": True, "voice_clone": False, "reference_audio": False,
            "voice_design": True, "voice_design_method": "native_instruct",
            "male": True, "female": True, "gender": True, "age": True, "pitch": True,
            "speed": True, "speed_range": {"min": 0.85, "max": 1.20, "step": 0.01},
            "modes": ["auto", "voice_design"],
        }

    def list_voices(self) -> list[dict[str, Any]]:
        return []

    @staticmethod
    def _instruction(options: dict[str, Any]) -> str | None:
        if options.get("mode") != "voice_design":
            return None
        design = options.get("design") if isinstance(options.get("design"), dict) else {}
        age = {"older adult": "elderly"}.get(str(design.get("age", "")), design.get("age"))
        values = [design.get("gender"), age, f"{design.get('pitch')} pitch" if design.get("pitch") else None]
        return ", ".join(str(value) for value in values if value)

    def generate_voice(self, request: VoiceGenerationRequest) -> Path:
        if not self.is_available():
            raise RuntimeError("Local OmniVoice runtime or model files are missing.")
        resource_error = self._resource_error()
        if resource_error:
            raise RuntimeError(resource_error)
        output = Path(request.output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model_path": str(self.model_path.resolve()), "output_path": str(output), "text": request.text,
            "language": request.language, "speed": float(request.options.get("speed", 1.0)),
            "instruct": self._instruction(request.options), "device": self.device, "num_step": 16,
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False, dir=output.parent) as handle:
            json.dump(payload, handle, ensure_ascii=False)
            request_file = Path(handle.name)
        environment = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
        try:
            completed = subprocess.run(
                [str(self.runtime_python), str(self.runner_path), str(request_file)], cwd=self.repo_root,
                env=environment, capture_output=True, text=True, encoding="utf-8", timeout=20 * 60,
            )
        except subprocess.TimeoutExpired as exc:
            output.unlink(missing_ok=True)
            raise RuntimeError("OmniVoice preview timed out after 20 minutes on CPU.") from exc
        finally:
            request_file.unlink(missing_ok=True)
        if completed.returncode != 0 or not output.is_file():
            output.unlink(missing_ok=True)
            detail = (completed.stderr or completed.stdout or "Unknown OmniVoice runtime error").strip().splitlines()[-1]
            raise RuntimeError(f"OmniVoice preview failed: {detail}")
        try:
            self.last_metrics = json.loads(completed.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            self.last_metrics = {"backend": "omnivoice_local"}
        return output

    def synthesize(self, request: VoiceGenerationRequest) -> VoiceSynthesisResult:
        output = self.generate_voice(request)
        duration, sample_rate = wav_metadata(output)
        return VoiceSynthesisResult(
            audio_file=output, provider=self.provider_id, voice_id=request.voice_id, language=request.language,
            duration=duration, sample_rate=sample_rate, engine=self.model_id,
        )
