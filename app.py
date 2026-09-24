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

from src.video.scene_source_manager import SceneVideoStore
from src.review.scene_video_review import serve_scene_video_review
from src.services.import_service import ImportService
from src.services.project_state import ProjectStateService
from src.services.render_service import RenderService
from src.services.narration_timeline import NarrationTimelineService
from src.services.voice_service import VoiceConfig, VoiceService
from src.services.voice_control import VoiceControlService
from src.services.agent_build import AgentBuildService, AgentBuildError
from src.services.script_service import ScriptService
from src.services.studio_project import LocalProjectManager
from src.studio_server import serve_studio
from src.providers.voice.registry import DEFAULT_VOICE_PROVIDER, ProviderRegistry
from src.review.voice_control_review import serve_voice_control

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
    source_videos = [
        path for path in (proj_dir / "scenes").glob("*/source/*")
        if path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
    ]
    audio = list((proj_dir / "audio").glob("*.wav")) + list((proj_dir / "voice" / "narration").glob("*.wav"))
    output = list((proj_dir / "output").glob("*.mp4")) + list((proj_dir / "render").rglob("*.mp4"))

    scene_slots = 0
    remotion = proj_dir / "remotion.json"
    if remotion.is_file():
        scene_slots = len(json.loads(remotion.read_text(encoding="utf-8")).get("scenes", []))
    print(f"  Scene slots:  {scene_slots}")
    print(f"  Scene images: {len(scenes)}")
    print(f"  Source clips: {len(source_videos)} versioned files")
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


def _run_remotion(project_name: str, studio: bool = False) -> None:
    """Launch the additive Remotion runtime without changing the Python environment."""
    proj_dir = ROOT_DIR / "projects" / project_name
    props_file = proj_dir / "remotion-props.json"
    if not props_file.exists():
        print(f"Error: Remotion props not found: {props_file}")
        sys.exit(1)

    node = shutil.which("node")
    cli = ROOT_DIR / "remotion" / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    if not node or not cli.is_file():
        print("Error: install the Remotion runtime first: pnpm --dir remotion install")
        sys.exit(1)

    relative_props = Path("..") / "projects" / project_name / "remotion-props.json"
    command = [node, str(cli)]
    if studio:
        command += ["studio", "src/index.ts", f"--props={relative_props.as_posix()}"]
    else:
        output = Path("..") / "projects" / project_name / "output" / "final_remotion.mp4"
        command += [
            "render", "src/index.ts", "TikTokExplainer", output.as_posix(),
            f"--props={relative_props.as_posix()}", "--codec=h264", "--audio-codec=aac",
            "--audio-bitrate=192k", "--pixel-format=yuv420p", "--width=1080", "--height=1920",
            "--fps=30", "--video-bitrate=10M", "--max-rate=12M", "--buffer-size=20M",
            "--x264-preset=medium", "--concurrency=25%",
        ]
    subprocess.run(command, cwd=ROOT_DIR / "remotion", check=True)


def _video_store(project_name: str) -> SceneVideoStore:
    try:
        return SceneVideoStore(ROOT_DIR, project_name)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)


def _print_video_record(record: dict) -> None:
    print(json.dumps(record, ensure_ascii=False, indent=2))


def _print_import_report(report: dict) -> None:
    print("IMPORT SUMMARY")
    print(f"Files found: {report['files_found']}")
    print(f"Valid files: {report['valid_files']}")
    print(f"Invalid files: {len(report['invalid_files'])}")
    print(f"Mapped scenes: {len(report['mapped_scenes'])}")
    print(f"Duplicate scenes: {len(report['duplicate_scenes'])}")
    print(f"Missing scenes: {', '.join(report['missing_scenes']) or 'none'}")
    print("\nSCENE MAP")
    for item in report["scene_map"]:
        probe = item["probe"]
        audio = item["source_audio"]
        print(
            f"{item['scene_id']}: {item['source_filename']} -> flow_v{item['version']} | "
            f"{probe['duration']}s {probe['width']}x{probe['height']} {probe['fps']}fps "
            f"audio={probe['has_audio']} mode={audio['mode']} volume={audio['volume']:.2f} status={item['status']}"
        )
    if report["warnings"]:
        print("\nWARNINGS")
        for warning in report["warnings"]:
            print(f"- {warning}")
    readiness = report["render_readiness"]
    print("\nRENDER READINESS")
    print(f"Approved: {readiness['approved']}")
    print(f"Pending review: {readiness['pending_review']}")
    print(f"Missing: {readiness['missing']}")
    print(f"Invalid: {readiness['invalid']}")
    print("\nSOURCE AUDIO")
    for item in report["source_audio"]:
        print(
            f"{item['scene_id']} v{item['version']}: has_audio={item['has_audio']} "
            f"mode={item['mode']} volume={item['volume']:.2f} duck={item['duck_under_narration']}"
        )
    print(f"\nReport: {report['report_path']}")

def main():
    parser = argparse.ArgumentParser(description="Video Animation Studio Master CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show project assets and state")
    status_parser.add_argument("project_name", help="Name of project (e.g. Astra_AI_Explainer)")

    exp_parser = subparsers.add_parser("export-project", help="Export full project backup")
    exp_parser.add_argument("project_name", help="Name of project")
    exp_parser.add_argument("--out", default="export", help="Output directory")

    new_project = subparsers.add_parser("new-project", help="Create an empty local AI Video Studio project")
    new_project.add_argument("name", help="Display name for the new project")
    new_project.add_argument("--id", help="Optional safe project id; defaults to a name-derived id")

    subparsers.add_parser("list-projects", help="List local project manifests")

    serve_studio_parser = subparsers.add_parser("serve-studio", help="Serve the local desktop UI and project API")
    serve_studio_parser.add_argument("--host", default="127.0.0.1")
    serve_studio_parser.add_argument("--port", type=int, default=8765)

    preview_parser = subparsers.add_parser("preview-video", help="Open a project in Remotion Studio")
    preview_parser.add_argument("project_name", help="Project with remotion-props.json")

    render_parser = subparsers.add_parser("render-video", help="Render a project through Remotion")
    render_parser.add_argument("project_name", help="Project with remotion-props.json")

    build_video = subparsers.add_parser(
        "build-video",
        help="Agent-first ZIP + script -> validated preview and final MP4",
        description="Run the complete unattended local pipeline: import, map, OmniVoice, subtitles, Remotion, FFmpeg, and ffprobe validation.",
    )
    build_video.add_argument("--zip", dest="zip_path", required=True, help="Google Flow source ZIP")
    build_video.add_argument("--script", dest="script_path", required=True, help="SCENE/Narration TXT script")
    build_video.add_argument("--project", dest="project_name", required=True, help="Project id or display name")
    build_video.add_argument("--config", dest="config_path", help="Optional project_config.json")
    build_video.add_argument("--use-existing-voice", action="store_true", help="TEST ONLY: reuse existing per-scene WAV files; never call OmniVoice")
    build_video.add_argument("--skip-voice", action="store_true", help="TEST ONLY: create silent WAVs; report is PARTIAL_PASS, never FULL_PASS")
    build_video.add_argument("--voice-timeout-seconds", type=float, default=20 * 60, help="Voice-stage warning threshold; long CPU inference is not killed early")
    build_video.add_argument("--voice-num-step", type=int, choices=[4, 8, 16], help="OmniVoice diffusion steps; production default is 8 (4 smoke test, 16 optional quality)")

    import_video = subparsers.add_parser("import-scene-video", help="Import a new immutable source-video version")
    import_video.add_argument("project_name")
    import_video.add_argument("--scene", required=True)
    import_video.add_argument("--file", required=True)
    import_video.add_argument("--provider", default="google_flow_manual")

    import_zip = subparsers.add_parser("import-flow-zip", help="Import and auto-map a Google Flow ZIP")
    import_zip.add_argument("project_name")
    import_zip.add_argument("zip_path")

    import_folder = subparsers.add_parser("import-flow-folder", help="Import and auto-map a Google Flow folder")
    import_folder.add_argument("project_name")
    import_folder.add_argument("folder_path")

    review_video = subparsers.add_parser("review-scene-video", help="Show prompt, clip versions, trim, crop, and review state")
    review_video.add_argument("project_name")
    review_video.add_argument("--scene", required=True)
    review_video.add_argument("--json", action="store_true", help="Print metadata instead of opening the browser UI")
    review_video.add_argument("--port", type=int, default=8811)
    review_video.add_argument("--no-open", action="store_true", help="Serve the UI without launching a browser")

    approve_video = subparsers.add_parser("approve-scene-video", help="Approve one source-video version")
    approve_video.add_argument("project_name")
    approve_video.add_argument("--scene", required=True)
    approve_video.add_argument("--version", type=int, required=True)

    reject_video = subparsers.add_parser("reject-scene-video", help="Reject one source-video version")
    reject_video.add_argument("project_name")
    reject_video.add_argument("--scene", required=True)
    reject_video.add_argument("--version", type=int, required=True)

    trim_video = subparsers.add_parser("trim-scene-video", help="Set non-destructive trim for one clip version")
    trim_video.add_argument("project_name")
    trim_video.add_argument("--scene", required=True)
    trim_video.add_argument("--version", type=int, required=True)
    trim_video.add_argument("--start", type=float, required=True)
    trim_video.add_argument("--end", type=float, required=True)

    crop_video = subparsers.add_parser("crop-scene-video", help="Set source-video crop focal point")
    crop_video.add_argument("project_name")
    crop_video.add_argument("--scene", required=True)
    crop_video.add_argument("--version", type=int, required=True)
    crop_video.add_argument("--x", type=float, required=True)
    crop_video.add_argument("--y", type=float, required=True)
    crop_video.add_argument("--mode", choices=["cover", "contain"], default="cover")

    source_audio = subparsers.add_parser("set-scene-audio", help="Set mute/background/full source audio policy")
    source_audio.add_argument("project_name")
    source_audio.add_argument("--scene", required=True)
    source_audio.add_argument("--version", type=int, required=True)
    source_audio.add_argument("--mode", choices=["mute", "background", "full"], required=True)
    source_audio.add_argument("--volume", type=float)
    source_audio.add_argument("--duck", choices=["true", "false"])
    source_audio.add_argument("--fade-in", type=float)
    source_audio.add_argument("--fade-out", type=float)

    transition = subparsers.add_parser("set-scene-transition", help="Override a scene transition")
    transition.add_argument("project_name")
    transition.add_argument("--scene", required=True)
    transition.add_argument("--transition", choices=["crossfade", "soft_slide", "wipe_reveal", "zoom_dissolve", "paper", "none"], required=True)

    source_speed = subparsers.add_parser("set-scene-video-speed", help="Set non-destructive source-video playback speed")
    source_speed.add_argument("project_name")
    source_speed.add_argument("--scene", required=True)
    source_speed.add_argument("--version", type=int, required=True)
    source_speed.add_argument("--speed", type=float, required=True, help="0.50 to 2.00")

    source_hold = subparsers.add_parser("set-scene-hold-last-frame", help="Enable or disable a final-frame hold")
    source_hold.add_argument("project_name")
    source_hold.add_argument("--scene", required=True)
    source_hold.add_argument("--version", type=int, required=True)
    source_hold.add_argument("--enabled", choices=["true", "false"], required=True)

    subtitle_offset = subparsers.add_parser("set-subtitle-offset", help="Move one scene subtitle vertically in pixels")
    subtitle_offset.add_argument("project_name")
    subtitle_offset.add_argument("--scene", required=True)
    subtitle_offset.add_argument("--y", type=int, required=True)

    render_preview = subparsers.add_parser("render-preview", help="Render a validated 720x1280 review MP4")
    render_preview.add_argument("project_name")

    narration = subparsers.add_parser("prepare-narration", help="Synthesize narration and build phrase subtitle timing")
    narration.add_argument("project_name")
    narration.add_argument("--reuse-audio", action="store_true")

    import_script = subparsers.add_parser("import-script", help="Import a TXT script and map SCENE blocks exactly")
    import_script.add_argument("project_name")
    import_script.add_argument("txt_path")

    set_script = subparsers.add_parser("set-scene-script", help="Set narration text for exactly one existing scene")
    set_script.add_argument("project_name")
    set_script.add_argument("--scene", type=int, required=True)
    set_script.add_argument("--text", required=True)

    approve_script = subparsers.add_parser("approve-script-mapping", help="Approve all mapped scene narration before voice generation")
    approve_script.add_argument("project_name")

    validate_project = subparsers.add_parser("validate-project", help="Show per-scene script/video readiness")
    validate_project.add_argument("project_name")

    subparsers.add_parser("voice-providers", help="Show lazy provider/voice/engine data for the future UI")

    voice_preview = subparsers.add_parser("voice-preview", help="Generate a short voice preview without video")
    voice_preview.add_argument("project_name")
    voice_preview.add_argument("--voice-id")
    voice_preview.add_argument("--text")
    voice_preview.add_argument("--out")

    voice_control = subparsers.add_parser("voice-control", help="Open the capability-aware voice preview panel")
    voice_control.add_argument("project_name")
    voice_control.add_argument("--port", type=int, default=8822)
    voice_control.add_argument("--no-open", action="store_true")

    comparisons = subparsers.add_parser("generate-voice-comparisons", help="Generate four male/female speed previews")
    comparisons.add_argument("project_name")

    select_voice = subparsers.add_parser("select-voice-preview", help="Select a preview and update project voice config")
    select_voice.add_argument("project_name")
    select_voice.add_argument("preview_id", choices=["male_1.08", "male_1.12", "female_1.08", "female_1.12"])

    approve_voice = subparsers.add_parser("approve-voice", help="Approve the selected voice without rendering video")
    approve_voice.add_argument("project_name")

    regenerate_voice = subparsers.add_parser("regenerate-approved-narration", help="Regenerate narration only after voice approval")
    regenerate_voice.add_argument("project_name")

    project_status = subparsers.add_parser("project-status", help="Show ZIP-first project workflow state")
    project_status.add_argument("project_name")

    approve_project = subparsers.add_parser("approve-project", help="Approve the current final review")
    approve_project.add_argument("project_name")

    approve_preview = subparsers.add_parser("approve-preview", help="Approve a watched preview before final render")
    approve_preview.add_argument("project_name")

    request_changes = subparsers.add_parser("request-changes", help="Mark the project as needing scene-level changes")
    request_changes.add_argument("project_name")
    request_changes.add_argument("--note", default="")

    args = parser.parse_args()
    if args.command == "status":
        show_status(args.project_name)
    elif args.command == "export-project":
        export_project(args.project_name, args.out)
    elif args.command == "new-project":
        _print_video_record(LocalProjectManager(ROOT_DIR).create(args.name, project_id=args.id))
    elif args.command == "list-projects":
        _print_video_record({"projects": LocalProjectManager(ROOT_DIR).list()})
    elif args.command == "serve-studio":
        serve_studio(ROOT_DIR, ROOT_DIR / "ui-prototype", args.host, args.port)
    elif args.command == "preview-video":
        _run_remotion(args.project_name, studio=True)
    elif args.command == "render-video":
        print(f"Final render: {RenderService(ROOT_DIR, args.project_name).render_final()}")
    elif args.command == "build-video":
        try:
            result = AgentBuildService(ROOT_DIR).build(
                zip_path=args.zip_path,
                script_path=args.script_path,
                project_name=args.project_name,
                config_path=args.config_path,
                use_existing_voice=args.use_existing_voice,
                skip_voice=args.skip_voice,
                voice_timeout_seconds=args.voice_timeout_seconds,
                voice_num_step=args.voice_num_step,
            )
        except AgentBuildError as exc:
            print(f"BUILD FAILED: {exc}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "import-scene-video":
        _print_video_record(_video_store(args.project_name).import_video(args.scene, args.file, args.provider, Path(args.file).name))
        print("STOP: video_status=pending_review. Approve or reject before final composition uses this clip.")
    elif args.command == "import-flow-zip":
        _print_import_report(ImportService(ROOT_DIR, args.project_name).import_zip(args.zip_path))
    elif args.command == "import-flow-folder":
        _print_import_report(ImportService(ROOT_DIR, args.project_name).import_folder(args.folder_path))
    elif args.command == "review-scene-video":
        store = _video_store(args.project_name)
        if args.json:
            _print_video_record(store.load_metadata(args.scene))
        else:
            serve_scene_video_review(store, args.scene, port=args.port, open_browser=not args.no_open)
    elif args.command == "approve-scene-video":
        _print_video_record(_video_store(args.project_name).approve(args.scene, args.version))
    elif args.command == "reject-scene-video":
        _print_video_record(_video_store(args.project_name).reject(args.scene, args.version))
    elif args.command == "trim-scene-video":
        _print_video_record(_video_store(args.project_name).set_trim(args.scene, args.version, args.start, args.end))
    elif args.command == "crop-scene-video":
        _print_video_record(_video_store(args.project_name).set_crop(args.scene, args.version, args.x, args.y, args.mode))
    elif args.command == "set-scene-audio":
        duck = None if args.duck is None else args.duck == "true"
        _print_video_record(_video_store(args.project_name).set_source_audio(
            args.scene, args.version, args.mode, args.volume, duck, args.fade_in, args.fade_out,
        ))
    elif args.command == "set-scene-transition":
        _print_video_record(_video_store(args.project_name).set_transition(args.scene, args.transition))
    elif args.command == "set-scene-video-speed":
        _print_video_record(_video_store(args.project_name).set_playback_speed(args.scene, args.version, args.speed))
    elif args.command == "set-scene-hold-last-frame":
        _print_video_record(_video_store(args.project_name).set_hold_last_frame(
            args.scene, args.version, args.enabled == "true",
        ))
    elif args.command == "set-subtitle-offset":
        _print_video_record(_video_store(args.project_name).set_subtitle_offset(args.scene, args.y))
    elif args.command == "render-preview":
        print(f"Preview render: {RenderService(ROOT_DIR, args.project_name).render_preview()}")
    elif args.command == "prepare-narration":
        _print_video_record(NarrationTimelineService(ROOT_DIR, args.project_name).prepare(synthesize=not args.reuse_audio))
    elif args.command == "import-script":
        _print_video_record(ScriptService(ROOT_DIR, args.project_name).import_text_file(args.txt_path))
    elif args.command == "set-scene-script":
        _print_video_record(ScriptService(ROOT_DIR, args.project_name).update_scene(args.scene, args.text))
    elif args.command == "approve-script-mapping":
        _print_video_record(ScriptService(ROOT_DIR, args.project_name).approve_mapping())
    elif args.command == "validate-project":
        _print_video_record({"scenes": ScriptService(ROOT_DIR, args.project_name).validation()})
    elif args.command == "voice-providers":
        _print_video_record({
            "default_voice_provider": "omnivoice",
            "providers": ProviderRegistry().catalog(),
        })
    elif args.command == "voice-preview":
        project_root = ROOT_DIR / "projects" / args.project_name
        source_path = project_root / "project.json"
        if not source_path.is_file():
            source_path = project_root / "narration.json"
        if not source_path.is_file():
            print(f"Error: Project voice config not found: {project_root}")
            sys.exit(1)
        voice_config = VoiceConfig.from_project(json.loads(source_path.read_text(encoding="utf-8")))
        # VoiceStudio is intentionally outside the current production scope.
        # A legacy project config is normalized before any provider is resolved.
        voice_config.provider = DEFAULT_VOICE_PROVIDER
        if args.voice_id:
            voice_config.voice_id = args.voice_id
        voice_service = VoiceService(project_root)
        if args.text:
            result = voice_service.generate_voice_preview(voice_config, args.text, args.out)
        else:
            result = voice_service.generate_voice_preview(voice_config, output_path=args.out)
        preview_report = result.to_dict()
        preview_report["warning"] = voice_service.last_warning
        preview_report["metrics"] = voice_service.last_metrics
        _print_video_record(preview_report)
    elif args.command == "voice-control":
        control = VoiceControlService(ROOT_DIR / "projects" / args.project_name)
        serve_voice_control(control, port=args.port, open_browser=not args.no_open)
    elif args.command == "generate-voice-comparisons":
        _print_video_record(VoiceControlService(ROOT_DIR / "projects" / args.project_name).generate_comparison_previews())
    elif args.command == "select-voice-preview":
        _print_video_record(VoiceControlService(ROOT_DIR / "projects" / args.project_name).select_preview(args.preview_id))
    elif args.command == "approve-voice":
        _print_video_record(VoiceControlService(ROOT_DIR / "projects" / args.project_name).approve_voice())
    elif args.command == "regenerate-approved-narration":
        _print_video_record(VoiceControlService(ROOT_DIR / "projects" / args.project_name).regenerate_narration())
    elif args.command == "project-status":
        _print_video_record(ProjectStateService(ROOT_DIR / "projects" / args.project_name).get())
    elif args.command == "approve-project":
        state = ProjectStateService(ROOT_DIR / "projects" / args.project_name)
        state.set("APPROVED", "final review approved")
        _print_video_record(state.set("DONE", "final MP4 ready for download"))
    elif args.command == "approve-preview":
        _print_video_record(RenderService(ROOT_DIR, args.project_name).approve_preview())
    elif args.command == "request-changes":
        _print_video_record(ProjectStateService(ROOT_DIR / "projects" / args.project_name).set("NEEDS_CHANGES", args.note))

if __name__ == "__main__":
    main()
