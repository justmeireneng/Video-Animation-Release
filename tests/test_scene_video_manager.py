import json
import tempfile
import unittest
from pathlib import Path

from src.video.scene_source_manager import SceneVideoStore
from src.services.narration_timeline import NarrationTimelineService


def fake_probe(path: Path, _repo_root: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    return {
        "duration": 6.2,
        "width": 1080,
        "height": 1920,
        "fps": 24.0,
        "codec": "h264",
        "pixel_format": "yuv420p",
        "has_audio": True,
        "audio_codec": "aac",
        "aspect_ratio": "1080:1920",
        "portrait": True,
    }


class TestSceneVideoStore(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        project = self.root / "projects" / "Demo"
        project.mkdir(parents=True)
        (project / "remotion.json").write_text(json.dumps({
            "name": "Demo",
            "fps": 30,
            "width": 1080,
            "height": 1920,
            "style": "cartoon_explainer",
            "mascot": {"idle": "mascot.png"},
            "scenes": [{
                "id": "scene_01",
                "index": 1,
                "approved": True,
                "durationInFrames": 180,
                "image": "scenes/scene_01.png",
                "narration": "Tiếng Việt rõ ràng.",
                "narrationAudio": "audio/scene_01.wav",
                "subtitle": [],
                "layout": "image_left_mascot_right",
                "mascotPose": "idle",
                "animation": {"type": "slow_push_in"},
                "focalPoint": {"x": 0.5, "y": 0.5},
                "transition": "none",
            }],
        }, ensure_ascii=False), encoding="utf-8")
        self.source = self.root / "source.mp4"
        self.source.write_bytes(b"test-video")
        self.store = SceneVideoStore(self.root, "Demo", prober=fake_probe)

    def tearDown(self):
        self.temp.cleanup()

    def test_import_never_overwrites_and_defaults_to_pending_background(self):
        first = self.store.import_video("scene_01", self.source)
        second = self.store.import_video("scene_01", self.source)
        self.assertEqual((first["version"], second["version"]), (1, 2))
        self.assertEqual(first["status"], "pending_review")
        self.assertEqual(first["source_audio"]["mode"], "background")
        self.assertTrue(first["source_audio"]["enabled"])
        self.assertEqual(first["source_audio"]["volume"], 0.30)
        self.assertEqual(first["source_video"], "scenes/scene_01/source/flow_v1.mp4")
        self.assertEqual(second["source_video"], "scenes/scene_01/source/flow_v2.mp4")
        self.assertTrue((self.store.project_root / first["source_video"]).exists())

    def test_approve_reject_and_rollback_sync_remotion(self):
        self.store.import_video("scene_01", self.source)
        self.store.import_video("scene_01", self.source)
        self.store.approve("scene_01", 2)
        self.store.reject("scene_01", 2)
        self.store.approve("scene_01", 1)
        project = json.loads(self.store.remotion_path.read_text(encoding="utf-8"))
        sources = project["scenes"][0]["videoSources"]
        self.assertEqual(next(item for item in sources if item["version"] == 1)["review"], "approved")
        self.assertEqual(next(item for item in sources if item["version"] == 2)["review"], "rejected")

    def test_trim_and_crop_are_non_destructive_metadata(self):
        self.store.import_video("scene_01", self.source)
        trimmed = self.store.set_trim("scene_01", 1, 0.2, 5.8)
        cropped = self.store.set_crop("scene_01", 1, 0.4, 0.6)
        self.assertEqual(trimmed["trim"], {"start": 0.2, "end": 5.8})
        self.assertEqual(cropped["crop"]["x"], 0.4)
        self.assertEqual(self.source.read_bytes(), b"test-video")

    def test_source_audio_modes_and_volume_are_scene_level(self):
        self.store.import_video("scene_01", self.source)
        muted = self.store.set_source_audio("scene_01", 1, "mute", 0.0)
        self.assertFalse(muted["source_audio"]["enabled"])
        full = self.store.set_source_audio("scene_01", 1, "full", 0.6, False, 0.1, 0.2)
        self.assertEqual(full["source_audio"]["mode"], "full")
        self.assertEqual(full["source_audio"]["volume"], 0.6)
        self.assertFalse(full["source_audio"]["duck_under_narration"])

    def test_manual_speed_and_hold_are_non_destructive_and_projected(self):
        self.store.import_video("scene_01", self.source)
        edited = self.store.set_playback_speed("scene_01", 1, 1.75)
        held = self.store.set_hold_last_frame("scene_01", 1, True)
        project = json.loads(self.store.remotion_path.read_text(encoding="utf-8"))
        source = project["scenes"][0]["videoSources"][0]
        self.assertEqual(edited["timing"]["playback_rate"], 1.75)
        self.assertTrue(edited["timing"]["manual_playback_rate"])
        self.assertTrue(held["timing"]["hold_last_frame"])
        self.assertEqual(source["playbackRate"], 1.75)
        self.assertTrue(source["holdLastFrame"])
        with self.assertRaises(ValueError):
            self.store.set_playback_speed("scene_01", 1, 2.01)
        self.assertEqual(self.source.read_bytes(), b"test-video")

    def test_subtitle_phrase_groups_stay_compact(self):
        phrases = NarrationTimelineService._phrases(
            "Đại Tây Dương không chỉ là một khoảng nước nằm giữa các lục địa."
        )
        self.assertEqual(" ".join(phrases), "Đại Tây Dương không chỉ là một khoảng nước nằm giữa các lục địa.")
        self.assertTrue(all(2 <= len(phrase.split()) <= 6 for phrase in phrases))

    def test_subtitle_phrase_groups_merge_single_word_clauses(self):
        text = "Nó giữ nhiệt, tạo mưa, rồi điều hòa khí hậu."
        phrases = NarrationTimelineService._phrases(text)
        self.assertEqual(" ".join(phrases), text)
        self.assertTrue(all(2 <= len(phrase.split()) <= 6 for phrase in phrases))


if __name__ == "__main__":
    unittest.main()
