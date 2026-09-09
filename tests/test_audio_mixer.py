#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.helpers import format_duration

class TestHelpers(unittest.TestCase):
    def test_duration_formatting(self):
        self.assertEqual(format_duration(70.78), "01:10.78")
        self.assertEqual(format_duration(6.5), "00:06.50")

if __name__ == "__main__":
    unittest.main()
