import json
import tempfile
import time
import unittest
from urllib.request import Request, urlopen
from pathlib import Path
from unittest.mock import patch

from src.providers.base import VoiceSynthesisResult
from src.services.import_service import ImportService
from src.services.script_service import ScriptService
from src.services.studio_project import LocalProjectManager
from src.services.render_service import RENDER_PRESETS, RemotionRenderer, RenderService
from src.services.voice_service import VoiceConfig, VoiceService
from src.studio_server import StudioApplication, StudioHTTPServer, run_server_in_thread


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

    def test_application_updates_only_the_selected_scene_script(self):
        self.manager.ensure_scene_slots(self.project_id, [1, 2])
        app = StudioApplication(self.root)
        app.update_scene_script(self.project_id, "scene_01", "Lời thoại riêng của cảnh một.")
        app.update_scene_script(self.project_id, "scene_02", "Lời thoại riêng của cảnh hai.")
        app.update_scene_script(self.project_id, "scene_02", "Cảnh hai đã được chỉnh lại.")

        detail = app.project(self.project_id)
        narration_by_id = {scene["id"]: scene["narration"] for scene in detail["scenes"]}
        self.assertEqual(narration_by_id["scene_01"], "Lời thoại riêng của cảnh một.")
        self.assertEqual(narration_by_id["scene_02"], "Cảnh hai đã được chỉnh lại.")
        self.assertIn('SCENE 1\nNarration:\n"Lời thoại riêng của cảnh một."', detail["script_text"])
        self.assertIn('SCENE 2\nNarration:\n"Cảnh hai đã được chỉnh lại."', detail["script_text"])

    def test_scene_script_route_updates_only_selected_scene(self):
        self.manager.ensure_scene_slots(self.project_id, [1, 2])
        app = StudioApplication(self.root)
        app.update_scene_script(self.project_id, "scene_01", "Cảnh một giữ nguyên.")
        ui_root = self.root / "ui"
        ui_root.mkdir()
        server, thread = run_server_in_thread(self.root, ui_root)
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/api/projects/{self.project_id}/scenes/scene_02/script"
            request = Request(url, data=json.dumps({"narration": "Cảnh hai qua HTTP."}).encode("utf-8"),
                              headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 200)
            scenes = app.project(self.project_id)["scenes"]
            self.assertEqual([scene["narration"] for scene in scenes], ["Cảnh một giữ nguyên.", "Cảnh hai qua HTTP."])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_local_server_refuses_duplicate_port(self):
        ui_root = self.root / "ui"
        ui_root.mkdir()
        server, thread = run_server_in_thread(self.root, ui_root)
        try:
            with self.assertRaises(OSError):
                StudioHTTPServer(("127.0.0.1", server.server_address[1]), object)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

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

    def test_local_render_api_prepares_narration_then_preview_and_requires_review_for_final(self):
        self.manager.ensure_scene_slots(self.project_id, [1])
        manifest = self.manager.load(self.project_id)
        manifest["script"]["approved"] = True
        manifest["voice"]["approved"] = True
        self.manager.save(self.project_id, manifest)
        remotion_path = self.project / "remotion.json"
        remotion = json.loads(remotion_path.read_text(encoding="utf-8"))
        remotion["scenes"][0]["narration"] = "Một cảnh thử."
        remotion_path.write_text(json.dumps(remotion), encoding="utf-8")
        metadata = self.project / "scenes" / "scene_01" / "metadata.json"
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text('{"approved_version": 1}', encoding="utf-8")
        app = StudioApplication(self.root)
        with self.assertRaisesRegex(Exception, "preview approval"):
            app.start_render(self.project_id, "final")
        with self.assertRaisesRegex(Exception, "Voice quality"):
            app.start_render(self.project_id, "preview", voice_steps=3)

        prepared = []

        def prepare(_service, *, synthesize=True, num_step=None, on_scene=None, included_scene_ids=None):
            self.assertEqual(num_step, 4)
            self.assertEqual(included_scene_ids, {"scene_01"})
            prepared.append(num_step)
            if on_scene:
                on_scene(1, 1, "scene_01")
            audio = self.project / "voice" / "narration" / "scene_01.wav"
            audio.write_bytes(b"RIFF-test-audio")
            return {"scenes": [{"scene_id": "scene_01"}]}

        def render(_renderer, _name, output, *, preview):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fake-mp4")
            return output

        def finalize(_finalizer, _source, output):
            output.write_bytes(b"fake-final-mp4")
            return output

        with patch("src.studio_server.NarrationTimelineService.prepare", autospec=True, side_effect=prepare), \
             patch.object(app, "_validate_voice_capacity"), \
             patch("src.services.render_service.RemotionRenderer.render", autospec=True, side_effect=render), \
             patch("src.services.render_service.FFmpegFinalizer.finalize", autospec=True, side_effect=finalize), \
             patch("src.services.render_service.FFmpegFinalizer.normalize_pixel_format", autospec=True, side_effect=lambda _finalizer, path, *, quality: path), \
             patch("src.services.render_service.RenderService._validate_output", autospec=True, return_value={"passed": True}):
            app.start_render(self.project_id, "preview")
            deadline = time.monotonic() + 5
            while app.render_status(self.project_id)["status"] == "running" and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(app.render_status(self.project_id)["status"], "complete")
            self.assertTrue(app.render_media_path(self.project_id, "preview").is_file())
            app.approve_render_preview(self.project_id)
            app.start_render(self.project_id, "final")
            deadline = time.monotonic() + 5
            while app.render_status(self.project_id)["status"] == "running" and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(app.render_status(self.project_id)["status"], "complete")
            self.assertTrue(app.render_media_path(self.project_id, "final").is_file())
            self.assertEqual(prepared, [4], "Final render must reuse approved narration audio")
            self.assertEqual(StudioApplication(self.root).render_status(self.project_id)["status"], "complete")
            ui_root = self.root / "ui"
            ui_root.mkdir()
            server, thread = run_server_in_thread(self.root, ui_root)
            server.RequestHandlerClass.app = app
            try:
                base = f"http://127.0.0.1:{server.server_address[1]}/api/projects/{self.project_id}/render"
                with urlopen(f"{base}/status", timeout=5) as response:
                    self.assertEqual(json.load(response)["status"], "complete")
                with urlopen(Request(f"{base}/final", headers={"Range": "bytes=0-3"}), timeout=5) as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.read(), b"fake")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_cut_decision_is_saved_and_excluded_from_render_config(self):
        self.manager.ensure_scene_slots(self.project_id, [1, 2])
        manifest = self.manager.load(self.project_id)
        manifest["script"]["approved"] = True
        manifest["voice"]["approved"] = True
        manifest["render"]["preview_ready"] = True
        self.manager.save(self.project_id, manifest)
        remotion_path = self.project / "remotion.json"
        remotion = json.loads(remotion_path.read_text(encoding="utf-8"))
        remotion["scenes"][0]["narration"] = "Giữ cảnh một."
        remotion["scenes"][1]["narration"] = "Cắt cảnh hai."
        remotion_path.write_text(json.dumps(remotion), encoding="utf-8")
        metadata = self.project / "scenes" / "scene_01" / "metadata.json"
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text('{"approved_version": 1}', encoding="utf-8")
        app = StudioApplication(self.root)
        updated = app.set_scene_decisions(self.project_id, {"scene_02": "cut"})
        self.assertTrue(updated["render"]["review_dirty"])
        self.assertFalse(updated["render"]["preview_approved"])
        renderer = RenderService(self.root, self.project_id)
        renderer._prepare_render_config(renderer._preflight(final=False, require_audio=False), "preview")
        render_config = json.loads((self.project / "render" / "render-remotion.json").read_text(encoding="utf-8"))
        self.assertEqual([scene["id"] for scene in render_config["scenes"]], ["scene_01"])
        self.assertEqual((render_config["width"], render_config["height"], render_config["fps"]), (720, 1280, 30))
        with self.assertRaisesRegex(Exception, "Keep at least one scene"):
            app.set_scene_decisions(self.project_id, {"scene_01": "cut"})

    def test_render_presets_and_ffprobe_validation_reject_wrong_resolution(self):
        self.assertEqual(
            (RENDER_PRESETS["preview"]["width"], RENDER_PRESETS["preview"]["height"], RENDER_PRESETS["preview"]["fps"]),
            (720, 1280, 30),
        )
        self.assertEqual(
            (RENDER_PRESETS["final"]["width"], RENDER_PRESETS["final"]["height"], RENDER_PRESETS["final"]["fps"]),
            (1080, 1920, 30),
        )
        output = self.project / "render" / "preview" / "preview.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake")
        wrong = {
            "duration": 2.0, "width": 540, "height": 960, "fps": 30.0, "codec": "h264",
            "pixel_format": "yuv420p", "video_bitrate": 5_000_000, "bitrate": 5_192_000,
            "has_audio": True, "audio_codec": "aac", "aspect_ratio": "540:960", "portrait": True,
            "readable": True,
        }
        renderer = RenderService(self.root, self.project_id)
        with patch("src.services.render_service.probe_video", return_value=wrong), \
             self.assertRaisesRegex(RuntimeError, "resolution 540x960"):
            renderer._validate_output(output, "preview", "preview")

    def test_remotion_command_renders_native_preset_without_scale(self):
        cli = self.root / "remotion" / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
        cli.parent.mkdir(parents=True)
        cli.write_text("", encoding="utf-8")
        renderer = RemotionRenderer(self.root)
        for preview, width, height, bitrate in ((True, 720, 1280, "5M"), (False, 1080, 1920, "10M")):
            output = self.project / "render" / ("preview" if preview else "final") / "test.mp4"
            with patch("src.services.render_service.shutil.which", return_value="node"), \
                 patch("src.services.render_service.subprocess.run") as run:
                run.return_value.returncode = 0
                renderer.render(self.project_id, output, preview=preview)
            command = run.call_args.args[0]
            self.assertIn(f"--width={width}", command)
            self.assertIn(f"--height={height}", command)
            self.assertIn("--fps=30", command)
            self.assertIn(f"--video-bitrate={bitrate}", command)
            self.assertIn("--pixel-format=yuv420p", command)
            self.assertTrue(any(argument.startswith("--concurrency=") for argument in command))
            concurrency = int(next(argument.split("=", 1)[1] for argument in command if argument.startswith("--concurrency=")))
            self.assertGreaterEqual(concurrency, 1)
            self.assertFalse(any(argument.startswith("--scale") for argument in command))

    def test_render_status_reports_interrupted_job_after_server_restart(self):
        status_file = self.project / "metadata" / "render-job.json"
        status_file.write_text(json.dumps({"status": "running", "quality": "preview", "step": 1,
                                          "progress": 12, "detail": "OmniVoice", "error": None}), encoding="utf-8")
        status = StudioApplication(self.root).render_status(self.project_id)
        self.assertEqual(status["status"], "failed")
        self.assertIn("stopped", status["error"])

    def test_project_edits_are_blocked_while_a_render_is_running(self):
        app = StudioApplication(self.root)
        app._render_jobs[self.project_id] = {"status": "running"}
        with self.assertRaisesRegex(Exception, "Wait for the current render"):
            app.save_script(self.project_id, "SCENE 1\nNarration:\n\"Changed\"")

    def test_render_voice_capacity_allows_cache_without_loading_model(self):
        self.manager.ensure_scene_slots(self.project_id, [1])
        remotion_path = self.project / "remotion.json"
        remotion = json.loads(remotion_path.read_text(encoding="utf-8"))
        remotion["scenes"][0]["narration"] = "Cached narration."
        remotion_path.write_text(json.dumps(remotion), encoding="utf-8")
        app = StudioApplication(self.root)
        unavailable = type("Unavailable", (), {"health_check": lambda self: {
            "ready_for_generation": False, "detail": "memory full",
        }})()
        with patch("src.studio_server.ProviderRegistry.get", return_value=unavailable):
            with self.assertRaisesRegex(Exception, "scene_01.*memory full"):
                app._validate_voice_capacity(self.project_id, 4)

        manifest = self.manager.load(self.project_id)
        config = VoiceConfig.from_project(manifest)
        config.options = {**config.options, "num_step": 4}
        service = VoiceService(self.project, fallback=False)
        key = service.cache_key("Cached narration.", config, selected_provider=config.provider)
        service.cache_root.mkdir(parents=True, exist_ok=True)
        (service.cache_root / f"{key}.wav").write_bytes(b"RIFF-cache")
        (service.cache_root / f"{key}.json").write_text("{}", encoding="utf-8")
        with patch("src.studio_server.ProviderRegistry.get", side_effect=AssertionError("Health must not run")):
            app._validate_voice_capacity(self.project_id, 4)

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
        cloned = StudioApplication(self.root).update_voice(self.project_id, {"mode": "voice_clone"})
        self.assertEqual(cloned["voice"]["mode"], "voice_clone")

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

    def test_voice_preview_uses_selected_scene_mapping_and_invalidates_after_script_edit(self):
        self.manager.ensure_scene_slots(self.project_id, [1, 2])
        app = StudioApplication(self.root)
        app.update_scene_script(self.project_id, "scene_01", "Lời thoại cảnh một.")
        app.update_scene_script(self.project_id, "scene_02", "Lời thoại cảnh hai.")

        def generate(service, config, sample_text, output_path=None):
            self.assertEqual(sample_text, "Lời thoại cảnh hai.")
            output = service.preview_root / "omnivoice-scene-two.wav"
            output.write_bytes(b"RIFF-scene-two")
            return VoiceSynthesisResult(output, "omnivoice", "default", config.language, 1.25, 24000)

        with patch("src.studio_server.VoiceService.generate_voice_preview", autospec=True, side_effect=generate):
            response = app.generate_voice_preview(self.project_id, {
                "scene_id": "scene_02", "text": "Lời thoại cảnh một.", "preview_scope": "full",
                "mode": "voice_design", "language": "vi", "gender": "male",
                "age": "young adult", "pitch": "moderate", "speed": 1.10,
            })
        self.assertEqual(response["scene_id"], "scene_02")
        self.assertEqual(self.manager.load(self.project_id)["voice"]["preview_scene_id"], "scene_02")

        app.update_scene_script(self.project_id, "scene_02", "Lời thoại cảnh hai đã đổi.")
        voice = self.manager.load(self.project_id)["voice"]
        self.assertIsNone(voice["preview_file"])
        self.assertIsNone(voice["preview_scene_id"])
        self.assertFalse(voice["approved"])
        with self.assertRaisesRegex(Exception, "Generate a voice preview"):
            app.approve_voice(self.project_id)

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
