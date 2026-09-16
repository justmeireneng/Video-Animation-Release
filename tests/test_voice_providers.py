#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.providers.base import VoiceGenerationRequest, VoiceProvider, VoiceSynthesisResult, wav_metadata
from src.providers.voice.omnivoice import OmniVoiceProvider
from src.providers.voice.registry import ProviderRegistry
from src.providers.voice.voicestudio_remote import RemoteVoiceStudioProvider
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
    provider_id = "voicestudio_remote"

    def is_available(self):
        return False

    def health_check(self):
        return {"available": False, "status": "not_installed_or_not_running"}


class FakeRemoteResponse:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None):
        self.body = body
        self.headers = headers or {}

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeRemoteEndpoint:
    """In-memory VoiceStudio protocol fixture; it never binds a localhost port."""

    def __init__(self):
        self.requests = []
        self.last_speech_payload = None

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        path = urlsplit(request.full_url).path
        if path == "/health":
            return FakeRemoteResponse(json.dumps({"status": "ok", "version": "test"}).encode("utf-8"))
        if path == "/v1/audio/voices":
            return FakeRemoteResponse(json.dumps({
                "voices": [{"voice_id": "profile-vi", "name": "Vietnamese profile", "language": "vi"}],
                "engines": [{"id": "runtime-engine", "available": True}],
            }).encode("utf-8"))
        if path == "/v1/audio/speech":
            self.last_speech_payload = json.loads(request.data.decode("utf-8"))
            return FakeRemoteResponse(wav_bytes(), {"X-VoiceStudio-Synthesis-Seconds": "0.321"})
        raise AssertionError(f"Unexpected remote path: {path}")


class TestVoiceProviders(unittest.TestCase):

    def test_omnivoice_keeps_existing_edge_fallback(self):
        request = VoiceGenerationRequest(text="Xin chào", output_path="expected.wav")
        with patch("src.providers.voice.edge_tts.EdgeTTSVoiceProvider.generate_voice", return_value=Path("expected.wav")) as generate:
            result = OmniVoiceProvider().generate_voice(request)
        self.assertEqual(result, Path("expected.wav"))
        generate.assert_called_once_with(request)

    def test_voicestudio_remote_requires_non_loopback_url(self):
        opener = FakeRemoteEndpoint()
        with patch.dict(os.environ, {}, clear=True):
            provider = RemoteVoiceStudioProvider(opener=opener)
        self.assertFalse(provider.is_available())
        self.assertEqual(provider.health_check()["status"], "remote_url_required_or_rejected")
        self.assertEqual(provider.list_voices(), [])
        self.assertEqual(opener.requests, [])
        loopback = RemoteVoiceStudioProvider(base_url="http://127.0.0.1:3900", opener=opener)
        self.assertFalse(loopback.is_available())
        self.assertIn("rejects localhost", loopback.health_check()["detail"])

    def test_voicestudio_remote_health_discovery_and_vietnamese_synthesis(self):
        endpoint = FakeRemoteEndpoint()
        provider = RemoteVoiceStudioProvider(
            base_url="https://voice.example.test", api_key="secret-for-test", timeout_seconds=12, opener=endpoint,
        )
        self.assertTrue(provider.health_check()["available"])
        self.assertEqual(provider.list_voices()[0]["voice_id"], "profile-vi")
        self.assertEqual(provider.list_engines()[0]["id"], "runtime-engine")
        self.assertEqual(provider.test_connection()["status"], "ready")
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
            self.assertEqual(endpoint.last_speech_payload["language"], "vi")
            self.assertEqual(endpoint.last_speech_payload["model"], "runtime-engine")
            self.assertEqual(endpoint.requests[-1][0].get_header("Authorization"), "Bearer secret-for-test")
            self.assertEqual(provider.last_metrics["remote_synthesis_seconds"], 0.321)
            self.assertEqual(provider.last_metrics["output_bytes"], len(wav_bytes()))

    def test_project_config_switch_and_legacy_config(self):
        switched = VoiceConfig.from_project({
            "voice": {
                "provider": "voicestudio_remote", "voice_id": "profile", "language": "vi", "speed": 1.1,
                "base_url": "https://voice.example.test", "timeout_seconds": 180, "api_key": "must-not-persist",
            }
        })
        self.assertEqual(switched.provider, "voicestudio_remote")
        self.assertEqual(switched.voice_id, "profile")
        self.assertEqual(switched.base_url, "https://voice.example.test")
        self.assertIsNone(switched.api_key)
        self.assertNotIn("api_key", switched.to_dict())
        legacy = VoiceConfig.from_project({"voice": "vi-VN-NamMinhNeural", "language": "vi-VN", "rate": "-8%"})
        self.assertEqual(legacy.provider, "omnivoice")
        self.assertAlmostEqual(legacy.speed, 0.92)

    def test_remote_cache_key_isolated_by_endpoint_and_excludes_api_key(self):
        service = VoiceService(Path(tempfile.gettempdir()), fallback=False)
        first = VoiceConfig(
            provider="voicestudio_remote", base_url="https://voice-a.example.test", api_key="first-secret",
            engine="tts-1", voice_id="profile", language="vi", speed=1.12,
        )
        second = VoiceConfig(
            provider="voicestudio_remote", base_url="https://voice-b.example.test", api_key="second-secret",
            engine="tts-1", voice_id="profile", language="vi", speed=1.12,
        )
        self.assertNotEqual(service.cache_key("Nội dung", first), service.cache_key("Nội dung", second))
        self.assertNotIn("secret", json.dumps(first.to_dict()))

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
        registry = ProviderRegistry({"omnivoice": FakeProvider, "voicestudio_remote": UnavailableProvider})
        resolution = registry.resolve("voicestudio_remote")
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
