import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.services.import_service import ImportService
from src.services.scene_mapper import SceneMapper


def fake_probe(path: Path, _repo_root: Path):
    if path.read_bytes() == b"corrupt":
        raise ValueError("unreadable test clip")
    return {
        "duration": 8.1,
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "codec": "h264",
        "pixel_format": "yuv420p",
        "has_audio": "silent" not in path.name.lower(),
        "audio_codec": "aac",
        "aspect_ratio": "1080:1920",
        "portrait": True,
        "readable": True,
    }


class TestFlowImport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        project = self.root / "projects" / "Demo"
        project.mkdir(parents=True)
        scenes = [
            {
                "id": f"shot_{number}",
                "index": number,
                "approved": True,
                "durationInFrames": 240,
                "image": f"scenes/shot_{number}.png",
                "narration": f"Scene {number}",
                "narrationAudio": f"audio/shot_{number}.wav",
                "subtitle": [],
                "layout": "image_left_mascot_right",
                "mascotPose": "idle",
                "animation": {"type": "slow_push_in"},
                "focalPoint": {"x": 0.5, "y": 0.5},
                "transition": "none",
            }
            for number in (1, 2, 10)
        ]
        (project / "remotion.json").write_text(json.dumps({
            "name": "Demo", "fps": 30, "width": 1080, "height": 1920,
            "style": "cartoon_explainer", "mascot": {"idle": "mascot.png"},
            "sourceVideoSettings": {"auto_approve_latest": False}, "scenes": scenes,
        }), encoding="utf-8")
        self.input = self.root / "input"
        self.input.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_regex_is_case_insensitive_and_sort_is_numeric(self):
        names = ["Scene_10_z.mp4", "scene-2-b.mp4", "SCENE 1 a.mp4"]
        for name in names:
            (self.input / name).write_bytes(b"video")
        detected, unmatched = SceneMapper.scan(self.input)
        self.assertEqual([item.number for item in detected], [1, 2, 10])
        self.assertEqual(unmatched, [])

    def test_folder_import_versions_duplicates_and_reports_missing(self):
        (self.input / "Scene_1_a.mp4").write_bytes(b"video-a")
        (self.input / "Scene_1_b.mp4").write_bytes(b"video-b")
        (self.input / "Scene_10_silent.mp4").write_bytes(b"video-c")
        (self.input / "no_scene.mp4").write_bytes(b"video-d")
        report = ImportService(self.root, "Demo", prober=fake_probe).import_folder(self.input)
        self.assertEqual([item["scene_number"] for item in report["scene_map"]], [1, 1, 10])
        self.assertEqual(report["duplicate_scenes"], {"scene_01": 2})
        self.assertEqual(report["missing_scenes"], ["shot_2"])
        self.assertEqual([item["version"] for item in report["scene_map"][:2]], [1, 2])
        self.assertEqual(report["scene_map"][2]["source_audio"]["mode"], "mute")
        self.assertTrue(Path(report["report_path"]).is_file())

    def test_zip_import_marks_corrupt_video_invalid_without_crashing(self):
        (self.input / "Scene_2_corrupt.mp4").write_bytes(b"corrupt")
        archive = self.root / "flow.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.write(self.input / "Scene_2_corrupt.mp4", "nested/Scene_2:corrupt.mp4")
        report = ImportService(self.root, "Demo", prober=fake_probe).import_zip(archive)
        self.assertEqual(len(report["invalid_files"]), 1)
        self.assertEqual(report["scene_map"][0]["status"], "invalid")
        self.assertEqual(report["scene_map"][0]["source_filename"], "Scene_2:corrupt.mp4")
        self.assertTrue((self.root / "projects" / "Demo" / "scenes" / "shot_2" / "source" / "flow_v1.mp4").is_file())

    def test_generic_flow_names_follow_zip_entry_order_and_require_review(self):
        archive = self.root / "flow-generic.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("Vertical_B.mp4", b"first")
            package.writestr("Vertical_A.mp4", b"second")
            package.writestr("notes.txt", "not media")
        report = ImportService(self.root, "Demo", prober=fake_probe).import_zip(archive)
        self.assertEqual(report["mapping_strategy"], "zip_order")
        self.assertTrue(report["mapping_requires_review"])
        self.assertEqual([(row["scene_number"], row["source_filename"]) for row in report["scene_map"]],
                         [(1, "Vertical_B.mp4"), (2, "Vertical_A.mp4")])
        self.assertEqual(report["files_found"], 2)
        self.assertEqual(report["valid_files"], 2)

    def test_zip_without_video_fails_clearly(self):
        archive = self.root / "empty-source.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("notes.txt", "no video")
        with self.assertRaisesRegex(ValueError, "No supported video"):
            ImportService(self.root, "Demo", prober=fake_probe).import_zip(archive)

    def test_non_video_zip_member_still_gets_path_safety_check(self):
        archive = self.root / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("../notes.txt", "unsafe")
        with self.assertRaisesRegex(ValueError, "Unsafe ZIP member"):
            ImportService(self.root, "Demo", prober=fake_probe).import_zip(archive)


if __name__ == "__main__":
    unittest.main()
