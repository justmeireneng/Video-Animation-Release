#!/usr/bin/env python3
"""
Example: Export a generation package for manual or browser upload to Google Flow / Veo.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main():
    proj_dir = ROOT / "projects" / "Astra_AI_Explainer"
    pkg_dir = ROOT / "flow_generation_package"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # Copy references
    ref_src = proj_dir / "references"
    ref_dst = pkg_dir / "references"
    if ref_src.exists():
        if ref_dst.exists():
            shutil.rmtree(ref_dst)
        shutil.copytree(ref_src, ref_dst)

    # Copy script and storyboard manifest
    shutil.copy2(proj_dir / "script" / "script.json", pkg_dir / "script.json")
    shutil.copy2(proj_dir / "storyboard" / "storyboard.json", pkg_dir / "storyboard.json")

    print(f"Flow generation package ready at: {pkg_dir}")

if __name__ == "__main__":
    main()
