#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import wave
import subprocess
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.providers.base import VoiceGenerationRequest, VoiceProvider, VoiceSynthesisResult, wav_metadata
from src.providers.voice.omnivoice import OmniVoiceProvider
from src.providers.voice.registry import ProviderRegistry
from src.services.narration_timeline import NarrationTimelineService
from src.services.voice_service import VoiceBatchItem, VoiceConfig, VoiceJobStatus, VoiceService


def wav_bytes(sample_rate: int = 16000, frames: int = 4000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00\x00" * frames)
    return output.getvalue()


class FakeProvider(VoiceProvider):
    provider_id = "fake"
    display_name = "Fake"

    def __init__(self):
        self.calls = 0

    def is_available(self):
        return True

    def health_check(self):
        return {"available": True, "status": "ok"}

    def capabilities(self):
        return {"synthesis": True}

    def list_voices(self):
        return [{"voice_id": "voice-1"}]

    def synthesize(self, request):
        self.calls += 1
        output = Path(request.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(wav_bytes())
        duration, sample_rate = wav_metadata(output)
        return VoiceSynthesisResult(output, self.provider_id, request.voice_id, request.language, duration, sample_rate)


class TestVoiceProviders(unittest.TestCase):

    def test_omnivoice_uses_isolated_local_runtime_without_edge_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime, runner, model = root / "python.exe", root / "runner.py", root / "model"
            runtime.write_bytes(b"")
            runner.write_text("", encoding="utf-8")
            (model / "audio_tokenizer").mkdir(parents=True)
            (model / "model.safetensors").write_bytes(b"model")
            (model / "audio_tokenizer" / "model.safetensors").write_bytes(b"tokenizer")
            output = root / "preview.wav"

            def run(command, **kwargs):
                request_file = Path(command[-1])
                payload = json.loads(request_file.read_text(encoding="utf-8"))
                Path(payload["output_path"]).write_bytes(wav_bytes())
                return subprocess.CompletedProcess(command, 0, '{"backend":"omnivoice_local"}\n', "")

            provider = OmniVoiceProvider(runtime_python=runtime, runner_path=runner, model_path=model)
            request = VoiceGenerationRequest(
                text="Xin chào", output_path=output,
                options={"mode": "voice_design", "speed": 1.12, "design": {"gender": "male", "age": "young adult", "pitch": "moderate"}},
            )
            with patch.dict(os.environ, {"OMNIVOICE_DISABLE_WARM_WORKER": "1"}), patch("src.providers.voice.omnivoice._memory_headroom", return_value={"physical": 4 * 1024**3, "commit": 6 * 1024**3}), patch("subprocess.run", side_effect=run):
                result = provider.generate_voice(request)
            self.assertEqual(result, output.resolve())
            self.assertEqual(provider.last_metrics["backend"], "omnivoice_local")

    def test_omnivoice_warm_worker_reuses_loaded_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner, model = root / "runner.py", root / "model"
            runner.write_text(
                "import json,sys,wave\n"
                "warm=False\n"
                "for line in sys.stdin:\n"
                " r=json.loads(line)\n"
                " with wave.open(r['output_path'],'wb') as a:\n"
                "  a.setnchannels(1);a.setsampwidth(2);a.setframerate(16000);a.writeframes(b'\\0\\0'*800)\n"
                " print(json.dumps({'ok':True,'metrics':{'backend':'omnivoice_local','warm_model':warm}}),flush=True)\n"
                " warm=True\n",
                encoding="utf-8",
            )
            (model / "audio_tokenizer").mkdir(parents=True)
            (model / "model.safetensors").write_bytes(b"model")
            (model / "audio_tokenizer" / "model.safetensors").write_bytes(b"tokenizer")
            provider = OmniVoiceProvider(runtime_python=sys.executable, runner_path=runner, model_path=model)
            request = VoiceGenerationRequest(text="Một", output_path=root / "one.wav", options={"mode": "auto"})
            try:
                with patch("src.providers.voice.omnivoice._memory_headroom", return_value={"physical": 4 * 1024**3, "commit": 6 * 1024**3}):
                    provider.generate_voice(request)
                    self.assertFalse(provider.last_metrics["warm_model"])
                    request.output_path = root / "two.wav"
                    provider.generate_voice(request)
                    self.assertTrue(provider.last_metrics["warm_model"])
            finally:
                OmniVoiceProvider.shutdown_warm_worker()

    def test_omnivoice_recovers_from_transient_warm_tokenizer_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime, runner, model = root / "python.exe", root / "runner.py", root / "model"
            runtime.write_bytes(b"")
            runner.write_text("", encoding="utf-8")
            (model / "audio_tokenizer").mkdir(parents=True)
            (model / "model.safetensors").write_bytes(b"model")
            (model / "audio_tokenizer" / "model.safetensors").write_bytes(b"tokenizer")
            output = root / "preview.wav"
            provider = OmniVoiceProvider(runtime_python=runtime, runner_path=runner, model_path=model)
            request = VoiceGenerationRequest(text="Xin chào", output_path=output, options={"mode": "auto"})

            def cold_retry(_payload, path):
                path.write_bytes(wav_bytes())
                return {"backend": "omnivoice_local", "warm_model": False}

            with (
                patch("src.providers.voice.omnivoice._memory_headroom", return_value={"physical": 4 * 1024**3, "commit": 6 * 1024**3}),
                patch.object(provider, "_worker_request", side_effect=RuntimeError("TypeError: TextEncodeInput must be Union[...]")),
                patch.object(provider, "_cold_request", side_effect=cold_retry) as retry,
                patch.object(OmniVoiceProvider, "shutdown_warm_worker") as shutdown,
            ):
                result = provider.generate_voice(request)

            self.assertEqual(result, output.resolve())
            self.assertTrue(provider.last_metrics["recovered_from_warm_worker"])
            shutdown.assert_called_once_with()
            retry.assert_called_once()

    def test_omnivoice_health_allows_pagefile_backed_low_memory_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime, runner, model = root / "python.exe", root / "runner.py", root / "model"
            runtime.write_bytes(b"")
            runner.write_text("", encoding="utf-8")
            (model / "audio_tokenizer").mkdir(parents=True)
            (model / "model.safetensors").write_bytes(b"model")
            (model / "audio_tokenizer" / "model.safetensors").write_bytes(b"tokenizer")
            provider = OmniVoiceProvider(runtime_python=runtime, runner_path=runner, model_path=model)
            with patch("src.providers.voice.omnivoice._memory_headroom", return_value={"physical": 512 * 1024**2, "commit": 2 * 1024**3}):
                health = provider.health_check()
            self.assertTrue(health["available"])
            self.assertTrue(health["ready_for_generation"])
            self.assertEqual(health["status"], "ready_low_memory")
            self.assertIn("reuse", health["detail"])
            self.assertEqual(health["memory"]["free_physical_gb"], 0.5)

    def test_omnivoice_health_blocks_when_commit_headroom_is_exhausted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime, runner, model = root / "python.exe", root / "runner.py", root / "model"
            runtime.write_bytes(b"")
            runner.write_text("", encoding="utf-8")
            (model / "audio_tokenizer").mkdir(parents=True)
            (model / "model.safetensors").write_bytes(b"model")
            (model / "audio_tokenizer" / "model.safetensors").write_bytes(b"tokenizer")
            provider = OmniVoiceProvider(runtime_python=runtime, runner_path=runner, model_path=model)
            with patch("src.providers.voice.omnivoice._memory_headroom", return_value={"physical": 200 * 1024**2, "commit": 600 * 1024**2}):
                health = provider.health_check()
            self.assertFalse(health["ready_for_generation"])
            self.assertEqual(health["status"], "memory_exhausted")

    def test_omnivoice_health_blocks_critically_low_physical_ram(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime, runner, model = root / "python.exe", root / "runner.py", root / "model"
            runtime.write_bytes(b"")
            runner.write_text("", encoding="utf-8")
            (model / "audio_tokenizer").mkdir(parents=True)
            (model / "model.safetensors").write_bytes(b"model")
            (model / "audio_tokenizer" / "model.safetensors").write_bytes(b"tokenizer")
            provider = OmniVoiceProvider(runtime_python=runtime, runner_path=runner, model_path=model)
            with patch("src.providers.voice.omnivoice._memory_headroom", return_value={"physical": 128 * 1024**2, "commit": 3 * 1024**3}):
                health = provider.health_check()
            self.assertFalse(health["ready_for_generation"])
            self.assertIn("free RAM", health["detail"])

    def test_default_registry_exposes_only_omnivoice(self):
        providers = ProviderRegistry().catalog()
        self.assertEqual([item["provider_id"] for item in providers], ["omnivoice"])

    def test_voice_config_defaults_to_omnivoice_design_and_legacy_rate(self):
        default = VoiceConfig()
        self.assertEqual(default.provider, "omnivoice")
        self.assertEqual(default.mode, "voice_design")
        self.assertEqual(default.design, {"gender": "male", "age": "young adult", "pitch": "moderate"})
        self.assertEqual(default.speed, 1.10)
        legacy = VoiceConfig.from_project({"voice": "vi-VN-NamMinhNeural", "language": "vi-VN", "rate": "-8%"})
        self.assertEqual(legacy.provider, "omnivoice")
        self.assertAlmostEqual(legacy.speed, 0.92)

    def test_cache_and_preview_do_not_need_video(self):
        fake = FakeProvider()
        registry = ProviderRegistry({"fake": lambda: fake})
        config = VoiceConfig(provider="fake", voice_id="voice-1", language="vi", speed=1.1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = VoiceService(root, registry=registry)
            first = service.synthesize("Cùng một nội dung", config, root / "one.wav")
            second = service.synthesize("Cùng một nội dung", config, root / "two.wav")
            preview = service.generate_voice_preview(config, "Đây là bản nghe thử.")
            self.assertFalse(first.cache_hit)
            self.assertTrue(second.cache_hit)
            self.assertEqual(fake.calls, 2)
            self.assertTrue(Path(preview.audio_file).is_file())
            self.assertFalse((root / "output" / "preview.mp4").exists())

    def test_strict_local_cache_works_without_loading_provider_again(self):
        fake = FakeProvider()
        registry = ProviderRegistry({"fake": lambda: fake})
        config = VoiceConfig(provider="fake", speed=1.1, options={"num_step": 4})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = VoiceService(root, registry=registry, fallback=False).synthesize("Nội dung đã tạo", config, root / "first.wav")
            with patch.object(registry, "resolve", side_effect=AssertionError("Model must not load on cache hit")):
                second = VoiceService(root, registry=registry, fallback=False).synthesize("Nội dung đã tạo", config, root / "second.wav")
            self.assertFalse(first.cache_hit)
            self.assertTrue(second.cache_hit)
            self.assertEqual(fake.calls, 1)
            self.assertEqual((root / "first.wav").read_bytes(), (root / "second.wav").read_bytes())

    def test_omnivoice_cache_key_tracks_active_voice_inputs(self):
        service = VoiceService(Path(tempfile.gettempdir()), fallback=False)
        base = VoiceConfig(
            provider="omnivoice", mode="voice_design", language="vi", speed=1.10,
            design={"gender": "male", "pitch": "moderate"},
        )
        self.assertEqual(service.cache_key("Nội dung", base), service.cache_key("Nội dung", base))
        variants = [
            VoiceConfig(provider="omnivoice", mode="auto", language="vi", speed=1.10),
            VoiceConfig(provider="omnivoice", mode="voice_design", language="vi", speed=1.10,
                        design={"gender": "female", "pitch": "moderate"}),
            VoiceConfig(provider="omnivoice", mode="voice_design", language="vi", speed=1.10,
                        design={"gender": "male", "pitch": "low"}),
            VoiceConfig(provider="omnivoice", mode="voice_design", language="vi", speed=1.12,
                        design={"gender": "male", "pitch": "moderate"}),
        ]
        for variant in variants:
            self.assertNotEqual(service.cache_key("Nội dung", base), service.cache_key("Nội dung", variant))
        self.assertNotEqual(service.cache_key("Nội dung", base), service.cache_key("Nội dung khác", base))
        detailed = VoiceConfig(provider="omnivoice", mode="voice_design", language="vi", speed=1.10,
                               design={"gender": "male", "pitch": "moderate"}, options={"num_step": 16})
        self.assertNotEqual(service.cache_key("Nội dung", base), service.cache_key("Nội dung", detailed))

    def test_invalid_provider_falls_back_with_clear_warning(self):
        registry = ProviderRegistry({"omnivoice": FakeProvider})
        resolution = registry.resolve("typo-provider")
        self.assertEqual(resolution.selected_provider, "omnivoice")
        self.assertIn("Unknown voice provider", resolution.warning)

    def test_inactive_provider_name_falls_back_without_loading_an_extra_provider(self):
        registry = ProviderRegistry({"omnivoice": FakeProvider})
        resolution = registry.resolve("inactive-provider")
        self.assertEqual(resolution.selected_provider, "omnivoice")
        self.assertIn("Unknown voice provider", resolution.warning)

    def test_batch_reports_scene_job_states(self):
        fake = FakeProvider()
        events = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = VoiceService(root, registry=ProviderRegistry({"fake": lambda: fake}))
            results = service.synthesize_batch(
                [
                    VoiceBatchItem("scene_01", "Một", root / "one.wav"),
                    VoiceBatchItem("scene_02", "Hai", root / "two.wav"),
                ],
                VoiceConfig(provider="fake"),
                lambda scene, status, error: events.append((scene, status, error)),
            )
        self.assertEqual([item["status"] for item in results], ["complete", "complete"])
        self.assertIn(("scene_01", VoiceJobStatus.QUEUED, None), events)
        self.assertIn(("scene_02", VoiceJobStatus.GENERATING, None), events)

    def test_atlantic_keeps_omnivoice_default(self):
        source = json.loads((ROOT / "projects" / "Atlantic_Ocean_Explainer" / "narration.json").read_text(encoding="utf-8"))
        config = VoiceConfig.from_project(source)
        self.assertEqual(config.provider, "omnivoice")
        self.assertEqual(config.mode, "voice_design")
        self.assertEqual(config.design, {"gender": "male", "age": "young adult", "pitch": "moderate"})
        self.assertEqual(config.speed, 1.10)
        self.assertTrue((ROOT / "projects" / "Atlantic_Ocean_Explainer" / "remotion.json").is_file())

    def test_narration_refresh_preserves_existing_visual_and_video_source_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            project = repo / "projects" / "demo"
            (project / "audio").mkdir(parents=True)
            (project / "audio" / "scene_01.wav").write_bytes(wav_bytes())
            (project / "narration.json").write_text(json.dumps({
                "voice": {"provider": "omnivoice", "voice_id": "voice-1", "language": "vi"},
                "scenes": [{"id": "scene_01", "narration": "Nội dung mới"}],
            }), encoding="utf-8")
            (project / "remotion.json").write_text(json.dumps({
                "fps": 30,
                "scenes": [{
                    "id": "scene_01",
                    "transition": "wipe_reveal",
                    "subtitleOffsetY": 123,
                    "videoSources": [{"src": "scenes/scene_01/source/flow_v1.mp4"}],
                    "currentVideoVersion": 1,
                }],
            }), encoding="utf-8")
            service = NarrationTimelineService(repo, "demo")
            with patch.object(service, "_audio_duration", return_value=1.0):
                service.prepare(synthesize=False)
            scene = json.loads((project / "remotion.json").read_text(encoding="utf-8"))["scenes"][0]
            self.assertEqual(scene["transition"], "wipe_reveal")
            self.assertEqual(scene["subtitleOffsetY"], 123)
            self.assertEqual(scene["videoSources"][0]["src"], "scenes/scene_01/source/flow_v1.mp4")
            self.assertEqual(scene["currentVideoVersion"], 1)


if __name__ == "__main__":
    unittest.main()
