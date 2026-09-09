#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.providers.base import ImageGenerationRequest, VideoGenerationRequest

class TestProviderInterfaces(unittest.TestCase):
    def test_image_request(self):
        req = ImageGenerationRequest(prompt="test cinematic prompt", resolution=(1080, 1920))
        self.assertEqual(req.aspect_ratio, "9:16")
        self.assertEqual(req.resolution, (1080, 1920))

    def test_video_request(self):
        req = VideoGenerationRequest(image_path="test.png", duration_s=5.0)
        self.assertEqual(req.duration_s, 5.0)
        self.assertEqual(req.fps, 24)

if __name__ == "__main__":
    unittest.main()
