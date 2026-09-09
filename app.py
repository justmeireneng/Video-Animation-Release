#!/usr/bin/env python3
"""
Video Animation Studio Master CLI.
Independent, standalone CLI for project management, inspection, and packaging.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

def show_status(project_name: str):
    proj_dir = ROOT_DIR / "projects" / project_name
    if not proj_dir.exists():
        print(f"Error: Project '{project_name}' not found at {proj_dir}")
        sys.exit(1)

    print(f"=== PROJECT STATUS: {project_name} ===")
    scenes = list((proj_dir / "scenes").glob("*.png"))
    audio = list((proj_dir / "audio").glob("*.wav"))
    output = list((proj_dir / "output").glob("*.mp4"))

    print(f"  Scenes count: {len(scenes)} images (1080x1920)")
    print(f"  Audio count:  {len(audio)} files")
    print(f"  Final videos: {len(output)} files")
    for vid in output:
        size_mb = vid.stat().st_size / (1024 * 1024)
        print(f"    -> {vid.name} ({size_mb:.2f} MB)")

def export_project(project_name: str, target_export_dir: Path | str = "export"):
    proj_dir = ROOT_DIR / "projects" / project_name
    if not proj_dir.exists():
        print(f"Error: Project '{project_name}' not found at {proj_dir}")
        sys.exit(1)

    exp_dir = ROOT_DIR / target_export_dir / project_name
    if exp_dir.exists():
        shutil.rmtree(exp_dir)
    exp_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== EXPORTING PROJECT '{project_name}' ===")
    print(f"Target: {exp_dir}")

    # Copy configs & docs
    shutil.copytree(ROOT_DIR / "config", exp_dir / "config")
    shutil.copytree(ROOT_DIR / "docs", exp_dir / "docs")
    print("  [?] Exported configs and documentation")

    # Copy project media & data
    for sub in ["script", "storyboard", "references", "scenes", "audio", "subtitles", "output"]:
        src_sub = proj_dir / sub
        if src_sub.exists():
            shutil.copytree(src_sub, exp_dir / sub)
            print(f"  [?] Exported {sub}/")

    manifest = {
        "project_name": project_name,
        "exported_at": "2026-09-09",
        "milestone": "v0.1.0-release",
        "files_count": sum(1 for _ in exp_dir.rglob("*") if _.is_file())
    }
    (exp_dir / "export_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"SUCCESS: Exported {manifest['files_count']} files to: {exp_dir}")

def main():
    parser = argparse.ArgumentParser(description="Video Animation Studio Master CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show project assets and state")
    status_parser.add_argument("project_name", help="Name of project (e.g. Astra_AI_Explainer)")

    exp_parser = subparsers.add_parser("export-project", help="Export full project backup")
    exp_parser.add_argument("project_name", help="Name of project")
    exp_parser.add_argument("--out", default="export", help="Output directory")

    args = parser.parse_args()
    if args.command == "status":
        show_status(args.project_name)
    elif args.command == "export-project":
        export_project(args.project_name, args.out)

if __name__ == "__main__":
    main()
