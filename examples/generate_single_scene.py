#!/usr/bin/env python3
"""
Example: Test generating a single 2.5D cinematic scene clip from an image.
"""
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.video.cinematic_engine import CinematicMotionEngine, MotionConfig, MotionType

def main():
    engine = CinematicMotionEngine(1080, 1920)
    img_path = ROOT / "projects" / "Astra_AI_Explainer" / "scenes" / "scene_01.png"
    out_mp4 = ROOT / "projects" / "Astra_AI_Explainer" / "output" / "example_clip.mp4"
    
    if not img_path.exists():
        print(f"Image not found: {img_path}")
        return

    cfg = MotionConfig(
        motion_type=MotionType.PUSH_IN,
        duration_s=4.0,
        fps=24,
        light_sweep=True,
        particles=True
    )
    print("Rendering single scene motion...")
    engine.render_clip(img_path, out_mp4, cfg)
    print(f"Generated: {out_mp4}")

if __name__ == "__main__":
    main()
