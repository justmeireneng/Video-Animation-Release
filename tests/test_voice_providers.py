#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import sys
import tempfile
import threading
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.providers.base import VoiceGenerationRequest, VoiceProvider, VoiceSynthesisResult, wav_metadata
from src.providers.voice.omnivoice import OmniVoiceProvider
from src.providers.voice.registry import ProviderRegistry
from src.providers.voice.voicestudio import VoiceStudioProvider
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


class UnavailableProvider(FakeProvider):
    provider_id = "voicestudio"

    def is_available(self):
        return False

    def health_check(self):
        return {"available": False, "status": "not_installed_or_not_running"}


class VoiceStudioHandler(BaseHTTPRequestHandler):
    last_speech_payload = None

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        if self.path == "/health":
            payload = {"status": "ok", "version": "test"}
        elif self.path == "/v1/audio/voices":
            payload = {
                "voices": [{"voice_id": "profile-vi", "name": "Vietnamese profile", "language": "vi"}],
                "engines": [{"id": "runtime-engine", "available": True}],
            }
        else:
            self.send_error(404)
            return
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/v1/audio/speech":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        type(self).last_speech_payload = json.loads(self.rfile.read(length).decode("utf-8"))
        body = wav_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TestVoiceProviders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), VoiceStudioHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_omnivoice_keeps_existing_edge_fallback(self):
        request = VoiceGenerationRequest(text="Xin chào", output_path="expected.wav")
        with patch("src.providers.voice.edge_tts.EdgeTTSVoiceProvider.generate_voice", return_value=Path("expected.wav")) as generate:
            result = OmniVoiceProvider().generate_voice(request)
        self.assertEqual(result, Path("expected.wav"))
        generate.assert_called_once_with(request)

    def test_voicestudio_absent_is_safe(self):
        provider = VoiceStudioProvider(base_url="http://127.0.0.1:1", timeout=0.05)
        self.assertFalse(provider.is_available())
        self.assertEqual(provider.list_voices(), [])

    def test_voicestudio_health_discovery_and_vietnamese_synthesis(self):
        provider = VoiceStudioProvider(base_url=self.base_url, timeout=1)
        self.assertTrue(provider.health_check()["available"])
        self.assertEqual(provider.list_voices()[0]["voice_id"], "profile-vi")
        self.assertEqual(provider.list_engines()[0]["id"], "runtime-engine")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "speech.wav"
            result = provider.synthesize(VoiceGenerationRequest(
                text="Xin chào Việt Nam",
                language="vi",
                voice_id="profile-vi",
                output_path=output,
                options={"engine": "runtime-engine", "speed": 1.1},
            ))
            self.assertEqual(result.audio_file, output)
            self.assertEqual(result.sample_rate, 16000)
            self.assertGreater(result.duration, 0)
            self.assertEqual(VoiceStudioHandler.last_speech_payload["language"], "vi")
            self.assertEqual(VoiceStudioHandler.last_speech_payload["model"], "runtime-engine")

    def test_project_config_switch_and_legacy_config(self):
        switched = VoiceConfig.from_project({
            "voice": {"provider": "voicestudio", "voice_id": "profile", "language": "vi", "speed": 1.1}
        })
        self.assertEqual(switched.provider, "voicestudio")
        self.assertEqual(switched.voice_id, "profile")
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

    def test_invalid_provider_falls_back_with_clear_warning(self):
        registry = ProviderRegistry({"omnivoice": FakeProvider})
        resolution = registry.resolve("typo-provider")
        self.assertEqual(resolution.selected_provider, "omnivoice")
        self.assertIn("Unknown voice provider", resolution.warning)

    def test_unavailable_optional_provider_falls_back_without_breaking_project(self):
        registry = ProviderRegistry({"omnivoice": FakeProvider, "voicestudio": UnavailableProvider})
        resolution = registry.resolve("voicestudio")
        self.assertEqual(resolution.selected_provider, "omnivoice")
        self.assertIn("unavailable", resolution.warning)

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
        self.assertEqual(config.voice_id, "vi-VN-NamMinhNeural")
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
