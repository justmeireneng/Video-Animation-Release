#!/usr/bin/env python3
"""Local bridge to the real k2-fsa OmniVoice runtime."""
from __future__ import annotations

import ctypes
import json
import os
import queue
import subprocess
import tempfile
import threading
import subprocess
from pathlib import Path
from typing import Any

from ..base import VoiceGenerationRequest, VoiceProvider, VoiceSynthesisResult, wav_metadata
from src.services.voice_service import PRODUCTION_VOICE_STEPS

COMFORTABLE_MEMORY_BYTES = 3 * 1024**3
MIN_COMMIT_HEADROOM_BYTES = 1 * 1024**3
MIN_PHYSICAL_HEADROOM_BYTES = 256 * 1024**2


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _memory_headroom() -> dict[str, int] | None:
    if os.name != "nt":
        return None
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return {
        "physical": int(status.ullAvailPhys),
        # Windows reports remaining commit capacity here (RAM + pagefile).
        "commit": int(status.ullAvailPageFile),
    }


class OmniVoiceProvider(VoiceProvider):
    provider_id = "omnivoice"
    display_name = "OmniVoice"
    _warm_worker: subprocess.Popen[str] | None = None
    _warm_worker_key: tuple[str, ...] | None = None
    _warm_worker_timer: threading.Timer | None = None
    _warm_worker_lock = threading.Lock()
    _detected_devices: dict[str, str] = {}

    def __init__(self, model_id: str = "k2-fsa/OmniVoice", device: str = "auto",
                 runtime_python: Path | str | None = None, model_path: Path | str | None = None,
                 runner_path: Path | str | None = None):
        self.model_id = model_id
        self.repo_root = Path(__file__).resolve().parents[3]
        self.runtime_python = Path(runtime_python) if runtime_python else self._default_runtime()
        self.model_path = Path(model_path) if model_path else self._default_model_path()
        self.runner_path = Path(runner_path) if runner_path else self.repo_root / "scripts" / "omnivoice_infer.py"
        self.device = self._detect_device(device)
        self.last_metrics: dict[str, Any] | None = None

    def _detect_device(self, requested: str) -> str:
        """Use a real runtime CUDA probe when auto mode is requested.

        OmniVoice's runner currently exposes CPU and CUDA device mapping and
        always uses fp16; bf16/int8/quantized paths are intentionally not
        advertised until the upstream runtime supports them.
        """
        if requested and requested not in {"auto", "default"}:
            return requested
        configured = os.environ.get("OMNIVOICE_DEVICE")
        if configured:
            return configured
        key = str(self.runtime_python.resolve())
        if key in type(self)._detected_devices:
            return type(self)._detected_devices[key]
        detected = "cpu"
        if self.runtime_python.is_file():
            try:
                result = subprocess.run(
                    [str(self.runtime_python), "-c", "import torch; print('cuda' if torch.cuda.is_available() else 'cpu')"],
                    capture_output=True, text=True, timeout=10, check=False,
                )
                candidate = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "cpu"
                if candidate == "cuda":
                    detected = "cuda"
            except (OSError, subprocess.SubprocessError):
                detected = "cpu"
        type(self)._detected_devices[key] = detected
        return detected

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
        headroom = _memory_headroom()
        if headroom is not None and os.environ.get("OMNIVOICE_ALLOW_LOW_MEMORY") != "1" and headroom["physical"] < MIN_PHYSICAL_HEADROOM_BYTES:
            return (
                f"OmniVoice cannot safely start with only {headroom['physical'] / 1024**3:.2f} GB of free RAM. "
                "Cached audio can still be reused; retry new narration when memory is available."
            )
        if headroom is not None and headroom["commit"] < MIN_COMMIT_HEADROOM_BYTES and os.environ.get("OMNIVOICE_ALLOW_LOW_MEMORY") != "1":
            return (
                f"OmniVoice cannot start because Windows has only {headroom['commit'] / 1024**3:.1f} GB of memory/pagefile headroom. "
                "Close one memory-heavy app and try Generate Preview again."
            )
        return None

    def _memory_detail(self) -> tuple[str, str | None, dict[str, float]]:
        headroom = _memory_headroom()
        if headroom is None:
            return "ready", None, {}
        values = {
            "free_physical_gb": round(headroom["physical"] / 1024**3, 2),
            "commit_headroom_gb": round(headroom["commit"] / 1024**3, 2),
        }
        if headroom["physical"] < COMFORTABLE_MEMORY_BYTES:
            return (
                "ready_low_memory",
                "Low-memory mode is available. The first CPU preview loads the model; subsequent previews reuse it briefly while memory permits.",
                values,
            )
        return "ready", None, values

    def is_available(self) -> bool:
        return self.runtime_python.is_file() and self.runner_path.is_file() and (self.model_path / "model.safetensors").is_file()

    def health_check(self) -> dict[str, Any]:
        resource_error = self._resource_error()
        memory_status, memory_detail, memory = self._memory_detail()
        available = self.is_available()
        ready = available and resource_error is None
        return {
            "available": available,
            "ready_for_generation": ready,
            "status": memory_status if ready else "memory_exhausted" if available else "not_installed",
            "provider": self.provider_id, "model_id": self.model_id, "model_path": str(self.model_path),
            "device": self.device, "runtime_backend": "omnivoice_local", "detail": resource_error or memory_detail,
            "memory": memory, "warm_worker": self._worker_is_alive(),
            "optimizations": {"fp16": True, "bf16": False, "int8": False, "quantization": False,
                               "batching": False, "chunked_inference": False, "lazy_loading": True},
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            # The bundled OmniVoice runtime exposes the native ref_audio/ref_text
            # cloning path.  Keep this capability truthful so the UI can expose
            # reference audio only when the active runtime actually supports it.
            "synthesis": True, "multilingual": True, "voice_clone": True, "reference_audio": True,
            "voice_design": True, "voice_design_method": "native_instruct",
            "male": True, "female": True, "gender": True, "age": True, "pitch": True,
            "speed": True, "speed_range": {"min": 0.85, "max": 1.20, "step": 0.01},
            "modes": ["auto", "voice_design", "voice_clone"],
        }

    def list_voices(self) -> list[dict[str, Any]]:
        return []

    @staticmethod
    def _instruction(options: dict[str, Any]) -> str | None:
        if options.get("mode") != "voice_design":
            return None
        design = options.get("design") if isinstance(options.get("design"), dict) else {}
        age = {"older adult": "elderly"}.get(str(design.get("age", "")), design.get("age"))
        # OmniVoice's native instruct parser accepts only its documented
        # pitch tokens.  Do not invent a "slightly low" variant: it causes
        # the whole voice stage to fail before any video render starts.
        pitch = {"low": "low", "moderate": "moderate", "high": "high"}.get(
            str(design.get("pitch")), design.get("pitch")
        )
        values = [design.get("gender"), age, f"{pitch} pitch" if pitch else None]
        return ", ".join(str(value) for value in values if value)

    @classmethod
    def _worker_is_alive(cls) -> bool:
        return cls._warm_worker is not None and cls._warm_worker.poll() is None

    @classmethod
    def _stop_worker_locked(cls) -> None:
        if cls._warm_worker_timer is not None:
            cls._warm_worker_timer.cancel()
            cls._warm_worker_timer = None
        worker = cls._warm_worker
        cls._warm_worker = None
        cls._warm_worker_key = None
        if worker is not None:
            if worker.poll() is None:
                try:
                    worker.terminate()
                except OSError:
                    pass
                try:
                    worker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        worker.kill()
                    except OSError:
                        pass
                    worker.wait(timeout=5)
            for stream in (worker.stdin, worker.stdout):
                if stream is not None and not stream.closed:
                    try:
                        stream.close()
                    except OSError:
                        pass

    @classmethod
    def shutdown_warm_worker(cls) -> None:
        with cls._warm_worker_lock:
            cls._stop_worker_locked()

    @classmethod
    def _schedule_worker_shutdown(cls) -> None:
        if cls._warm_worker_timer is not None:
            cls._warm_worker_timer.cancel()
        configured = os.environ.get("OMNIVOICE_WARM_TTL_SECONDS")
        if configured is not None:
            ttl = max(60, int(configured))
        else:
            headroom = _memory_headroom()
            low_memory = headroom is not None and (
                headroom["physical"] < 1536 * 1024**2 or headroom["commit"] < 2 * 1024**3
            )
            ttl = 120 if low_memory else 600
        timer = threading.Timer(ttl, cls.shutdown_warm_worker)
        timer.daemon = True
        cls._warm_worker_timer = timer
        timer.start()

    def _worker_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        cls = type(self)
        worker_key = (str(self.runtime_python.resolve()), str(self.runner_path.resolve()),
                      str(self.model_path.resolve()), self.device)
        with cls._warm_worker_lock:
            if not cls._worker_is_alive() or cls._warm_worker_key != worker_key:
                cls._stop_worker_locked()
                environment = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
                cls._warm_worker = subprocess.Popen(
                    [str(self.runtime_python), str(self.runner_path), "--serve"], cwd=self.repo_root,
                    env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
                )
                cls._warm_worker_key = worker_key
            worker = cls._warm_worker
            if worker is None or worker.stdin is None or worker.stdout is None:
                raise RuntimeError("OmniVoice warm worker could not start.")
            try:
                worker.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                worker.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                cls._stop_worker_locked()
                raise RuntimeError("OmniVoice warm worker stopped unexpectedly.") from exc

            response_queue: queue.Queue[str] = queue.Queue(maxsize=1)
            reader = threading.Thread(target=lambda: response_queue.put(worker.stdout.readline()), daemon=True)
            reader.start()
            try:
                response_line = response_queue.get(timeout=20 * 60)
            except queue.Empty as exc:
                cls._stop_worker_locked()
                raise RuntimeError("OmniVoice preview timed out after 20 minutes on CPU.") from exc
            if not response_line:
                cls._stop_worker_locked()
                raise RuntimeError("OmniVoice warm worker exited before returning audio.")
            try:
                response = json.loads(response_line)
            except json.JSONDecodeError as exc:
                cls._stop_worker_locked()
                raise RuntimeError("OmniVoice warm worker returned an invalid response.") from exc
            if not response.get("ok"):
                raise RuntimeError(f"OmniVoice preview failed: {response.get('error', 'Unknown worker error')}")
            cls._schedule_worker_shutdown()
            return dict(response.get("metrics") or {})

    def _cold_request(self, payload: dict[str, Any], output: Path) -> dict[str, Any]:
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
            raise RuntimeError("OmniVoice preview timed out after 20 minutes on CPU.") from exc
        finally:
            request_file.unlink(missing_ok=True)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "Unknown OmniVoice runtime error").strip().splitlines()[-1]
            raise RuntimeError(f"OmniVoice preview failed: {detail}")
        try:
            return json.loads(completed.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return {"backend": "omnivoice_local", "warm_model": False}

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
            "instruct": self._instruction(request.options), "device": self.device,
            "num_step": max(4, min(32, int(request.options.get("num_step", PRODUCTION_VOICE_STEPS)))),
            "ref_audio": str(Path(request.ref_audio).resolve()) if request.ref_audio else None,
            "ref_text": request.options.get("reference_text") or None,
        }
        try:
            if os.environ.get("OMNIVOICE_DISABLE_WARM_WORKER") == "1":
                self.last_metrics = self._cold_request(payload, output)
            else:
                try:
                    self.last_metrics = self._worker_request(payload)
                except RuntimeError as exc:
                    # OmniVoice/Transformers can very occasionally leave the
                    # retained tokenizer in an invalid state between requests.
                    # A clean process succeeds with the same text, so recover
                    # once automatically instead of making the user retry the
                    # whole render from the UI.
                    if "TextEncodeInput" not in str(exc):
                        raise
                    type(self).shutdown_warm_worker()
                    self.last_metrics = self._cold_request(payload, output)
                    self.last_metrics["recovered_from_warm_worker"] = True
        except RuntimeError:
            output.unlink(missing_ok=True)
            raise
        if not output.is_file():
            output.unlink(missing_ok=True)
            raise RuntimeError("OmniVoice worker completed without creating an audio file.")
        return output

    def synthesize(self, request: VoiceGenerationRequest) -> VoiceSynthesisResult:
        output = self.generate_voice(request)
        duration, sample_rate = wav_metadata(output)
        return VoiceSynthesisResult(
            audio_file=output, provider=self.provider_id, voice_id=request.voice_id, language=request.language,
            duration=duration, sample_rate=sample_rate, engine=self.model_id,
        )
