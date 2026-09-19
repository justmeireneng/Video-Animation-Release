"""Standalone narration stage for the agent-first pipeline.

This module is deliberately independent from Remotion and FFmpeg. It owns
voice generation, cache/resume behavior, progress logging, and the explicit
test-only existing/silent voice modes.
"""
from __future__ import annotations

import json
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.providers.voice.registry import ProviderRegistry
from src.services.narration_timeline import NarrationTimelineService


class VoiceStageError(RuntimeError):
    pass


class VoiceGenerationStage:
    """Generate or reuse one WAV per scene and build subtitle timing."""

    def __init__(self, repo_root: Path | str, project_name: str):
        self.repo_root = Path(repo_root).resolve()
        self.project_name = project_name
        self.project_root = self.repo_root / "projects" / project_name

    def _manifest(self) -> dict[str, Any]:
        return json.loads((self.project_root / "project.json").read_text(encoding="utf-8"))

    def _silent_audio(self, path: Path, text: str) -> None:
        # A deterministic, short silent track is only for --skip-voice smoke
        # tests; it is never used by the default production build.
        duration = max(0.5, min(30.0, len(text.split()) * 0.34 + 0.35))
        sample_rate = 16_000
        frames = int(round(duration * sample_rate))
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(b"\0\0" * frames)

    def _scene_audio_paths(self) -> list[tuple[str, str, Path]]:
        remotion = json.loads((self.project_root / "remotion.json").read_text(encoding="utf-8"))
        result: list[tuple[str, str, Path]] = []
        for scene in sorted(remotion.get("scenes", []), key=lambda item: int(item.get("index", 0))):
            text = str(scene.get("narration", "")).strip()
            if not text:
                continue
            relative = str(scene.get("narrationAudio") or f"voice/narration/{scene['id']}.wav")
            result.append((str(scene["id"]), text, self.project_root / relative))
        return result

    def run(
        self,
        *,
        use_existing_voice: bool = False,
        skip_voice: bool = False,
        num_step: int | None = None,
        timeout_seconds: float = 20 * 60,
        on_progress: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        if use_existing_voice and skip_voice:
            raise VoiceStageError("--use-existing-voice and --skip-voice are mutually exclusive.")
        if timeout_seconds <= 0:
            raise VoiceStageError("voice_timeout_seconds must be greater than zero.")
        scenes = self._scene_audio_paths()
        if not scenes:
            raise VoiceStageError("No scene narration is available for voice generation.")

        started = time.perf_counter()
        stage_status = "GENERATED"
        warnings: list[str] = []
        provider_report: dict[str, Any] = {"provider": "omnivoice"}
        if skip_voice:
            stage_status = "SKIPPED"
            for scene_id, text, output in scenes:
                self._silent_audio(output, text)
            warnings.append("Voice generation was skipped; silent WAVs were created for smoke testing only.")
        elif use_existing_voice:
            stage_status = "REUSED"
            missing = [scene_id for scene_id, _, output in scenes if not output.is_file()]
            if missing:
                raise VoiceStageError(f"Existing voice mode requires WAV files for: {', '.join(missing)}")
            warnings.append("Existing narration WAVs were reused; OmniVoice was not called.")
        else:
            provider = ProviderRegistry().get("omnivoice")
            health = provider.health_check()
            device = str(health.get("device") or "cpu")
            provider_report = {
                "provider": "omnivoice", "device": device, "health": health,
                "capabilities": provider.capabilities(),
                "optimization_audit": {
                    "cuda": device.startswith("cuda"), "fp16": True,
                    "bf16": False, "int8": False, "quantization": False,
                    "batching": False, "chunked_inference": False,
                    "lazy_loading": True, "basis": "scripts/omnivoice_infer.py",
                },
            }
            if device == "cpu":
                warnings.append("OmniVoice is running on CPU. Narration generation may be slow.")
            if on_progress:
                on_progress(f"Voice stage: {len(scenes)} scene(s), device={device}")
            timeline = NarrationTimelineService(self.repo_root, self.project_name)
            sequence = {scene_id: index for index, (scene_id, _, _) in enumerate(scenes, 1)}
            active: dict[str, float] = {}
            progress_events: list[dict[str, Any]] = []
            live_log = self.project_root / "metadata" / "logs" / "voice-progress.json"
            live_log.parent.mkdir(parents=True, exist_ok=True)

            def progress(index: int, total: int, scene_id: str) -> None:
                now = time.perf_counter()
                if scene_id not in active:
                    active[scene_id] = now
                    progress_events.append({"scene_id": scene_id, "index": sequence.get(scene_id, index), "status": "generating", "started_at": datetime.now(timezone.utc).isoformat(), "device": provider_report.get("device", "cpu"), "output_path": str(self.project_root / f"voice/narration/{scene_id}.wav")})
                    if on_progress:
                        on_progress(f"Generating voice {sequence.get(scene_id, index)}/{total}: {scene_id}")
                else:
                    elapsed = round(now - active.pop(scene_id), 3)
                    progress_events.append({"scene_id": scene_id, "index": sequence.get(scene_id, index), "status": "complete", "elapsed_seconds": elapsed, "finished_at": datetime.now(timezone.utc).isoformat(), "device": provider_report.get("device", "cpu"), "output_path": str(self.project_root / f"voice/narration/{scene_id}.wav")})
                    if on_progress:
                        on_progress(f"Voice ready {sequence.get(scene_id, index)}/{total}: {scene_id} ({elapsed}s)")
                live_log.write_text(json.dumps({"status": "running", "scenes": progress_events}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            result = timeline.prepare(synthesize=True, num_step=num_step, on_scene=progress)
            elapsed = time.perf_counter() - started
            if elapsed > timeout_seconds:
                warnings.append(f"Voice stage exceeded configured timeout ({timeout_seconds:.0f}s) but completed; no partial audio was discarded.")
            report_path = self.project_root / "narration-report.json"
            if report_path.is_file():
                try:
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    report = result
            else:
                report = result
            scene_reports = report.get("scenes", [])
            for item in scene_reports:
                voice = item.get("voice", {})
                item["device"] = voice.get("device") or provider_report.get("device", "cpu")
                item["output_path"] = str(self.project_root / f"voice/narration/{item['scene_id']}.wav")
            report["stage"] = "voice"
            report["status"] = stage_status
            report["warnings"] = warnings
            report["provider"] = provider_report
            report["elapsed_seconds"] = round(elapsed, 3)
            report["progress"] = progress_events
            (self.project_root / "metadata" / "logs").mkdir(parents=True, exist_ok=True)
            (self.project_root / "metadata" / "logs" / "voice-stage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return {"status": stage_status, "provider": provider_report, "warnings": warnings, "scenes": scene_reports, "elapsed_seconds": round(elapsed, 3), "report": report}

        # Existing/silent modes still run the normal subtitle timing builder,
        # but never call a provider.
        timeline_result = NarrationTimelineService(self.repo_root, self.project_name).prepare(synthesize=False)
        elapsed = time.perf_counter() - started
        scene_reports = timeline_result.get("scenes", [])
        for item in scene_reports:
            item["device"] = "none" if skip_voice else "existing"
            item["output_path"] = str(self.project_root / f"voice/narration/{item['scene_id']}.wav")
            item.setdefault("voice", {})["cache_hit"] = not skip_voice
        report = {
            "stage": "voice", "status": stage_status, "provider": provider_report,
            "warnings": warnings, "scenes": scene_reports, "elapsed_seconds": round(elapsed, 3),
        }
        (self.project_root / "metadata" / "logs").mkdir(parents=True, exist_ok=True)
        (self.project_root / "metadata" / "logs" / "voice-stage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
