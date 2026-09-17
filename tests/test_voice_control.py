#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import wave
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.providers.base import VoiceProvider, VoiceSynthesisResult, wav_metadata
from src.providers.voice.registry import ProviderRegistry
from src.review.voice_control_review import _form_text, voice_control_page
from src.services.narration_timeline import NarrationTimelineService
from src.services.voice_control import VoiceControlError, VoiceControlService, VOICE_PREVIEW_TEXT
from src.services.voice_service import VoiceConfig, VoiceService
from src.video.scene_source_manager import SceneVideoStore


def wav_bytes(sample_rate: int = 16000, frames: int = 1600) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00\x00" * frames)
    return output.getvalue()


class DesignProvider(VoiceProvider):
    provider_id = "omnivoice"
    display_name = "OmniVoice"

    def __init__(self):
        self.calls = 0

    def is_available(self):
        return True

    def health_check(self):
        return {"available": True, "status": "ready"}

    def capabilities(self):
        return {
            "synthesis": True,
            "modes": ["auto", "voice_design"],
            "voice_design": True,
            "gender": True,
            "age": False,
            "pitch": True,
            "speed": True,
            "speed_range": {"min": 0.85, "max": 1.20, "step": 0.01},
            "voice_clone": False,
            "reference_audio": False,
        }

    def list_voices(self):
        return [
            {"voice_id": "vi-VN-NamMinhNeural", "name": "Nam Minh"},
            {"voice_id": "vi-VN-HoaiMyNeural", "name": "Hoài My"},
        ]

    def synthesize(self, request):
        self.calls += 1
        output = Path(request.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(wav_bytes())
        duration, sample_rate = wav_metadata(output)
        gender = request.options.get("design", {}).get("gender", "male")
        voice_id = "vi-VN-HoaiMyNeural" if gender == "female" else "vi-VN-NamMinhNeural"
        return VoiceSynthesisResult(output, self.provider_id, voice_id, request.language, duration, sample_rate)


class TestVoiceControl(unittest.TestCase):
    def make_control(self, root: Path):
        project = root / "projects" / "demo"
        project.mkdir(parents=True)
        (root / "config").mkdir()
        (root / "config" / "voice_profiles.json").write_text('{"profiles": []}', encoding="utf-8")
        (project / "narration.json").write_text(json.dumps({
            "language": "vi",
            "voice": {"provider": "omnivoice", "mode": "auto", "language": "vi", "speed": 1.0},
            "scenes": [{"id": "scene_01", "narration": "Xin chào"}],
        }), encoding="utf-8")
        design = DesignProvider()
        registry = ProviderRegistry({"omnivoice": lambda: design})
        return VoiceControlService(project, registry=registry), design

    def test_ui_contract_hides_unsupported_age_and_clone_and_has_audio_player(self):
        with tempfile.TemporaryDirectory() as tmp:
            control, _ = self.make_control(Path(tmp))
            control.update_state(mode="voice_design")
            contract = control.ui_contract()
            self.assertEqual([provider["provider_id"] for provider in contract["providers"]], ["omnivoice"])
            self.assertTrue(contract["controls"]["gender"]["visible"])
            self.assertFalse(contract["controls"]["age"]["visible"])
            self.assertNotIn("voice_clone", contract["controls"]["mode"]["options"])
            page = voice_control_page(control)
            self.assertIn("VOICE ENGINE", page)
            self.assertIn("1.10 Default", page)
            self.assertNotIn('name="provider"', page)
            self.assertNotIn("VoiceStudio", page)
            self.assertNotIn("Clone reference audio", page)
            self.assertIn('<audio id="active-preview" controls', page)
            self.assertIn("Generate 4 comparisons", page)

    def test_voice_form_decodes_vietnamese_as_utf8(self):
        expected = VOICE_PREVIEW_TEXT
        part = BytesParser(policy=default).parsebytes(
            b"Content-Type: text/plain\r\nMIME-Version: 1.0\r\n\r\n" + expected.encode("utf-8")
        )
        self.assertEqual(_form_text(part), expected)

    def test_validation_rejects_bad_speed_clone_and_unsupported_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            control, _ = self.make_control(Path(tmp))
            with self.assertRaisesRegex(VoiceControlError, "Speed"):
                control.validate(VoiceConfig(provider="omnivoice", speed=1.3))
            with self.assertRaisesRegex(VoiceControlError, "voice_clone"):
                control.validate(VoiceConfig(provider="omnivoice", mode="voice_clone", speed=1.0))
            with self.assertRaisesRegex(VoiceControlError, "age design"):
                control.validate(VoiceConfig(
                    provider="omnivoice", mode="voice_design", speed=1.0,
                    design={"gender": "male", "age": "young adult", "pitch": "moderate"},
                ))
            with self.assertRaisesRegex(VoiceControlError, "Only OmniVoice"):
                control.update_state(provider="future-provider")

    def test_four_previews_and_selection_update_config_without_video_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            control, provider = self.make_control(Path(tmp))
            report = control.generate_comparison_previews()
            names = {Path(item["file"]).name for item in report["previews"]}
            self.assertEqual(names, {"male_1.08.wav", "male_1.12.wav", "female_1.08.wav", "female_1.12.wav"})
            self.assertEqual(provider.calls, 4)
            self.assertFalse((control.project_root / "output" / "final.mp4").exists())
            selected = control.select_preview("female_1.12")
            self.assertEqual(selected["provider"], "omnivoice")
            self.assertEqual(selected["design"]["gender"], "female")
            self.assertEqual(selected["speed"], 1.12)
            self.assertFalse(selected["approved"])
            with self.assertRaisesRegex(RuntimeError, "awaiting approval"):
                NarrationTimelineService(control.project_root.parents[1], "demo").prepare(synthesize=True)
            approved = control.approve_voice()
            self.assertTrue(approved["approved"])

    def test_omnivoice_speed_uses_native_rate_without_changing_pitch(self):
        captured = []

        def generate(_provider, request):
            captured.append(request)
            output = Path(request.output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(wav_bytes())
            return output

        with tempfile.TemporaryDirectory() as tmp, patch(
            "src.providers.voice.omnivoice.OmniVoiceProvider.generate_voice", autospec=True, side_effect=generate
        ):
            root = Path(tmp)
            service = VoiceService(root, fallback=False)
            for speed in (1.08, 1.12):
                service.synthesize(
                    VOICE_PREVIEW_TEXT,
                    VoiceConfig(
                        provider="omnivoice", mode="voice_design", language="vi", speed=speed,
                        design={"gender": "female", "pitch": "moderate"},
                    ),
                    root / f"female_{speed:.2f}.wav",
                )
        self.assertEqual([item.options["speed"] for item in captured], [1.08, 1.12])
        self.assertEqual([item.pitch for item in captured], ["+0Hz", "+0Hz"])
        self.assertEqual({item.voice_id for item in captured}, {"default"})

    def test_shorter_narration_retimes_projection_by_trimming_not_speeding_visual(self):
        item = {
            "source_video": "scene.mp4", "source_provider": "flow", "source_filename": "scene.mp4",
            "version": 1, "status": "approved", "probe": {"duration": 8.0},
            "trim": {"start": 0.0, "end": None}, "crop": {"mode": "cover", "x": 0.5, "y": 0.5},
            "timing": {"playback_rate": 1.0, "hold_last_frame": True, "loop": False},
            "source_audio": {"mode": "background"},
        }
        projection = SceneVideoStore._source_projection(item, target_duration=6.0)
        self.assertEqual(projection["trim"]["end"], 6.0)
        self.assertEqual(projection["playbackRate"], 1.0)
        self.assertFalse(projection["holdLastFrame"])


if __name__ == "__main__":
    unittest.main()
