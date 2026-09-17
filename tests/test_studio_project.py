import json
import tempfile
import unittest
from urllib.request import Request, urlopen
from pathlib import Path
from unittest.mock import patch

from src.providers.base import VoiceSynthesisResult
from src.services.import_service import ImportService
from src.services.script_service import ScriptService
from src.services.studio_project import LocalProjectManager
from src.services.render_service import RenderService
from src.studio_server import StudioApplication, run_server_in_thread


def fake_probe(_path: Path, _repo_root: Path):
    return {
        "duration": 7.2,
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "codec": "h264",
        "pixel_format": "yuv420p",
        "has_audio": True,
        "audio_codec": "aac",
        "aspect_ratio": "1080:1920",
        "portrait": True,
        "readable": True,
    }


class TestStudioProject(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manager = LocalProjectManager(self.root)
        self.manifest = self.manager.create("New documentary", project_id="new-documentary")
        self.project_id = self.manifest["id"]
        self.project = self.root / "projects" / self.project_id

    def tearDown(self):
        self.temp.cleanup()

    def test_creates_documented_layout_and_dynamic_scene_gaps(self):
        for relative in (
            "source/imported", "source/scenes", "script", "voice/previews", "voice/narration", "voice/cache",
            "subtitles/scenes", "subtitles/final", "audio/bgm", "audio/sfx", "audio/temp",
            "render/preview", "render/final", "metadata/probes", "metadata/logs",
        ):
            self.assertTrue((self.project / relative).is_dir(), relative)
        self.assertEqual(self.manifest["voice"]["provider"], "omnivoice")
        self.assertEqual(self.manifest["voice"]["speed"], 1.10)
        self.manager.ensure_scene_slots(self.project_id, [2, 10])
        remotion = json.loads((self.project / "remotion.json").read_text(encoding="utf-8"))
        self.assertEqual([scene["index"] for scene in remotion["scenes"]], list(range(1, 11)))
        self.assertEqual(remotion["scenes"][-1]["id"], "scene_10")

    def test_import_builds_scene_slots_from_mov_names_without_reindexing(self):
        source = self.root / "flow"
        source.mkdir()
        (source / "Scene_03.mov").write_bytes(b"media")
        report = ImportService(self.root, self.project_id, prober=fake_probe).import_folder(source)
        remotion = json.loads((self.project / "remotion.json").read_text(encoding="utf-8"))
        self.assertEqual([scene["id"] for scene in remotion["scenes"]], ["scene_01", "scene_02", "scene_03"])
        self.assertEqual(report["missing_scenes"], ["scene_01", "scene_02"])
        self.assertEqual(report["scene_map"][0]["source_extension"], ".mov")
        self.assertTrue((self.project / "scenes" / "scene_03" / "source" / "flow_v1.mov").is_file())

    def test_generic_zip_creates_scene_slots_and_exposes_mapping_in_project_api(self):
        import zipfile
        archive = self.root / "flow.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("Flow_Second.mp4", b"clip2")
            package.writestr("Flow_First.mp4", b"clip1")
        report = ImportService(self.root, self.project_id, prober=fake_probe).import_zip(archive)
        self.assertEqual([row["scene_id"] for row in report["scene_map"]], ["scene_01", "scene_02"])
        detail = StudioApplication(self.root).project(self.project_id)
        self.assertEqual(detail["last_import_report"]["mapping_strategy"], "zip_order")
        self.assertEqual([row["source_filename"] for row in detail["last_import_report"]["scene_map"]],
                         ["Flow_Second.mp4", "Flow_First.mp4"])

    def test_script_maps_exact_scene_numbers_and_requires_complete_approval(self):
        self.manager.ensure_scene_slots(self.project_id, [1, 3])
        service = ScriptService(self.root, self.project_id)
        result = service.save_bulk('SCENE 1\nNarration:\n"Một."\n\nSCENE 3\nNarration:\n"Ba."')
        self.assertEqual(result["mapped_scene_numbers"], [1, 3])
        with self.assertRaises(ValueError):
            service.approve_mapping()
        service.update_scene(2, "Hai.")
        approved = service.approve_mapping()
        self.assertTrue(approved["script"]["approved"])
        self.assertEqual(approved["status"], "VOICE_SETUP")
        validation = service.validation()
        self.assertTrue(all(item["script"] == "SCRIPT_OK" for item in validation))

    def test_final_render_preflight_requires_preview_approval(self):
        self.manager.ensure_scene_slots(self.project_id, [1])
        service = ScriptService(self.root, self.project_id)
        service.update_scene(1, "Nội dung đã duyệt.")
        service.approve_mapping()
        manifest = self.manager.load(self.project_id)
        manifest["voice"]["approved"] = True
        self.manager.save(self.project_id, manifest)
        scene_root = self.project / "scenes" / "scene_01"
        scene_root.mkdir(parents=True)
        (scene_root / "metadata.json").write_text(json.dumps({"approved_version": 1, "versions": []}), encoding="utf-8")
        narration = self.project / "voice" / "narration" / "scene_01.wav"
        narration.write_bytes(b"placeholder")
        renderer = RenderService(self.root, self.project_id)
        self.assertEqual(renderer._preflight(final=False)["id"], self.project_id)
        with self.assertRaisesRegex(RuntimeError, "preview approval"):
            renderer._preflight(final=True)

    def test_local_server_lists_real_projects_and_never_uses_mock_seeds(self):
        app = StudioApplication(self.root)
        self.assertEqual(app.list_projects()[0]["id"], self.project_id)
        detail = app.project(self.project_id)
        self.assertEqual(detail["project"]["id"], self.project_id)
        ui_root = self.root / "ui"
        ui_root.mkdir()
        (ui_root / "index.html").write_text("<title>Local Studio</title>", encoding="utf-8")
        server, thread = run_server_in_thread(self.root, ui_root)
        try:
            port = server.server_address[1]
            with urlopen(f"http://127.0.0.1:{port}/api/projects", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["projects"][0]["id"], self.project_id)
            with urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
                self.assertIn(b"Local Studio", response.read())
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_local_source_preview_supports_video_byte_ranges(self):
        source = self.root / "Scene_1.mp4"
        source.write_bytes(b"clip-video")
        ImportService(self.root, self.project_id, prober=fake_probe).import_folder(self.root)
        ui_root = self.root / "ui"
        ui_root.mkdir()
        server, thread = run_server_in_thread(self.root, ui_root)
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/api/projects/{self.project_id}/scenes/scene_01/source"
            with urlopen(Request(url, headers={"Range": "bytes=1-3"}), timeout=5) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.headers["Content-Range"], "bytes 1-3/10")
                self.assertEqual(response.read(), b"lip")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_local_api_persists_only_supported_omnivoice_controls(self):
        updated = StudioApplication(self.root).update_voice(self.project_id, {
            "mode": "voice_design", "language": "vi", "gender": "female", "pitch": "high", "speed": 1.12,
        })
        self.assertEqual(updated["voice"]["provider"], "omnivoice")
        self.assertEqual(updated["voice"]["design"], {"gender": "female", "age": "young adult", "pitch": "high"})
        self.assertFalse(updated["voice"]["approved"])
        with self.assertRaisesRegex(Exception, "does not support mode"):
            StudioApplication(self.root).update_voice(self.project_id, {"mode": "voice_clone"})

    def test_voice_preview_is_persisted_and_required_before_approval(self):
        app = StudioApplication(self.root)
        with self.assertRaisesRegex(Exception, "Generate a voice preview"):
            app.approve_voice(self.project_id)

        def generate(service, config, sample_text, output_path=None):
            self.assertEqual(config.options["num_step"], 4)
            self.assertLessEqual(len(sample_text), 48)
            output = service.preview_root / "omnivoice-test.wav"
            output.write_bytes(b"RIFF-local-preview")
            return VoiceSynthesisResult(output, "omnivoice", "default", config.language, 1.25, 24000)

        with patch("src.studio_server.VoiceService.generate_voice_preview", autospec=True, side_effect=generate):
            response = app.generate_voice_preview(self.project_id, {
                "text": "Đây là bản đọc thử.", "mode": "voice_design", "language": "vi",
                "gender": "male", "age": "young adult", "pitch": "moderate", "speed": 1.10,
            })
        self.assertEqual(response["provider"], "omnivoice")
        self.assertEqual(response["preview_scope"], "quick")
        self.assertEqual(response["audio_url"], f"/api/projects/{self.project_id}/voice/preview")
        self.assertTrue(app.voice_preview_path(self.project_id).is_file())
        approved = app.approve_voice(self.project_id)
        self.assertTrue(approved["voice"]["approved"])
        self.assertEqual(approved["status"], "READY_TO_RENDER")

    def test_quick_preview_clips_long_text_but_full_preview_keeps_it(self):
        app = StudioApplication(self.root)
        text = "Hàn Quốc là nơi những cung điện cổ, khu phố truyền thống và lịch sử lâu đời cùng tồn tại."
        heard = []

        def generate(service, config, sample_text, output_path=None):
            heard.append(sample_text)
            output = service.preview_root / f"preview-{len(heard)}.wav"
            output.write_bytes(b"RIFF-local-preview")
            return VoiceSynthesisResult(output, "omnivoice", "default", config.language, 1.25, 24000)

        with patch("src.studio_server.VoiceService.generate_voice_preview", autospec=True, side_effect=generate):
            quick = app.generate_voice_preview(self.project_id, {"text": text, "preview_scope": "quick"})
            full = app.generate_voice_preview(self.project_id, {"text": text, "preview_scope": "full"})
        self.assertLessEqual(len(quick["preview_text"]), 48)
        self.assertEqual(quick["preview_text"], heard[0])
        self.assertEqual(full["preview_text"], text)
        self.assertEqual(heard[1], text)


if __name__ == "__main__":
    unittest.main()
