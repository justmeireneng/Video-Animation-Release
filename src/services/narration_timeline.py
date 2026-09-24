from __future__ import annotations

import json
import math
import re
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from src.providers.base import wav_metadata
from src.services.voice_service import PRODUCTION_VOICE_STEPS, VoiceConfig, VoiceService
from src.video.scene_source_manager import SceneVideoStore, find_ffprobe


VOICE_SPEED_FIT_FORBIDDEN = "VOICE_SPEED_FIT_FORBIDDEN"


class NarrationTimelineService:
    """Build narration audio and phrase subtitles without changing storyboard source files."""

    def __init__(self, repo_root: Path | str, project_name: str):
        self.repo_root = Path(repo_root).resolve()
        self.project_name = project_name
        self.project_root = self.repo_root / "projects" / project_name
        self.source_path = self.project_root / "narration.json"
        self.remotion_path = self.project_root / "remotion.json"
        if not self.project_root.is_dir() or (not self.remotion_path.is_file() and not self.source_path.is_file()):
            raise FileNotFoundError(f"Project narration/remotion data not found: {self.project_root}")

    @staticmethod
    def _phrases(text: str) -> list[str]:
        groups: list[str] = []
        clauses = re.split(r"(?<=[.!?;,])\s+", text.strip())
        for clause in clauses:
            words = clause.split()
            if not words:
                continue
            count = max(1, math.ceil(len(words) / 6))
            while count > 1 and len(words) // count < 2:
                count -= 1
            base, extra = divmod(len(words), count)
            offset = 0
            for index in range(count):
                size = base + (1 if index < extra else 0)
                groups.append(" ".join(words[offset:offset + size]))
                offset += size
        index = 0
        while len(groups) > 1 and index < len(groups):
            if len(groups[index].split()) != 1:
                index += 1
                continue
            if index > 0 and len(groups[index - 1].split()) < 6:
                groups[index - 1] = f"{groups[index - 1]} {groups[index]}"
                groups.pop(index)
                index = max(0, index - 1)
                continue
            if index + 1 < len(groups) and len(groups[index + 1].split()) < 6:
                groups[index] = f"{groups[index]} {groups.pop(index + 1)}"
                index += 1
                continue
            if index > 0:
                previous = groups[index - 1].split()
                groups[index - 1] = " ".join(previous[:-1])
                groups[index] = f"{previous[-1]} {groups[index]}"
            else:
                following = groups[index + 1].split()
                groups[index] = f"{groups[index]} {following[0]}"
                groups[index + 1] = " ".join(following[1:])
            index += 1
        return groups

    def _audio_duration(self, path: Path) -> float:
        result = subprocess.run(
            [str(find_ffprobe(self.repo_root)), "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            check=True, capture_output=True, text=True, encoding="utf-8",
        )
        return float(result.stdout.strip())

    @staticmethod
    def _subtitle_timing(phrases: list[str], duration: float, fps: int,
                         offset_frames: int = 0) -> list[dict[str, Any]]:
        total_words = sum(len(phrase.split()) for phrase in phrases)
        frame_end = max(1, round(duration * fps))
        cursor = 0
        result: list[dict[str, Any]] = []
        consumed = 0
        for index, phrase in enumerate(phrases):
            consumed += len(phrase.split())
            end = frame_end if index == len(phrases) - 1 else round(frame_end * consumed / total_words)
            end = max(cursor + 1, end)
            result.append({"startFrame": cursor + offset_frames, "endFrame": end + offset_frames, "text": phrase})
            cursor = end
        return result

    def prepare(self, *, synthesize: bool = True, num_step: int | None = None,
                on_scene: Callable[[int, int, str], None] | None = None,
                included_scene_ids: set[str] | None = None) -> dict[str, Any]:
        existing_project = json.loads(self.remotion_path.read_text(encoding="utf-8")) if self.remotion_path.is_file() else {}
        if self.source_path.is_file():
            # Legacy narration.json remains supported for established projects.
            source = json.loads(self.source_path.read_text(encoding="utf-8"))
        else:
            # In projects created by the desktop workflow the approved script
            # already lives in remotion.json; do not duplicate or rewrite it.
            manifest_path = self.project_root / "project.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
            source = {
                "title": manifest.get("name", existing_project.get("name", self.project_name)),
                "voice": manifest.get("voice", {}),
                "scenes": [
                    {"id": scene["id"], "narration": scene.get("narration", ""), "intent": scene.get("intent", "")}
                    for scene in existing_project.get("scenes", [])
                    if str(scene.get("narration", "")).strip()
                ],
            }
            if not source["scenes"]:
                raise ValueError("No approved scene script is available for narration.")
        remotion_path = self.remotion_path
        existing_scenes = {str(item.get("id")): item for item in existing_project.get("scenes", [])}
        fps = 30
        pre_roll = max(0.0, float(source.get("pre_roll_seconds", 0.15)))
        post_roll = max(0.0, float(source.get("post_roll_seconds", source.get("scene_pause_seconds", 0.25))))
        pre_roll_frames = round(pre_roll * fps)
        is_desktop_project = (self.project_root / "project.json").is_file()
        audio_root = self.project_root / ("voice/narration" if is_desktop_project else "audio")
        audio_root.mkdir(parents=True, exist_ok=True)
        voice_config = VoiceConfig.from_project(source)
        if num_step is not None:
            if num_step not in {4, 8, 16}:
                raise ValueError("OmniVoice narration quality must use 4, 8 or 16 steps.")
            voice_config.options = {**voice_config.options, "num_step": num_step}
        elif "num_step" not in voice_config.options:
            voice_config.options = {**voice_config.options, "num_step": PRODUCTION_VOICE_STEPS}
        if synthesize and voice_config.approval_required and not voice_config.approved:
            raise RuntimeError("Voice selection is awaiting approval; narration was not regenerated.")
        # Desktop projects may use only the explicitly selected local provider.
        # Never replace a failed OmniVoice render with a cloud or mock voice.
        voice_service = VoiceService(self.project_root, fallback=not is_desktop_project)
        source_store = SceneVideoStore(self.repo_root, self.project_name)
        scenes: list[dict[str, Any]] = []
        report: list[dict[str, Any]] = []
        transitions = ["crossfade", "soft_slide", "crossfade", "paper"]
        selected_total = sum(included_scene_ids is None or str(item["id"]) in included_scene_ids for item in source["scenes"])
        selected_index = 0
        # OmniVoice voice-design calls can choose a different timbre on each
        # generation.  Keep scene 1 as the user's chosen baseline and use its
        # rendered WAV as a stable clone reference for all following scenes.
        voice_anchor: Path | None = None
        voice_anchor_text: str | None = None
        first_scene = source["scenes"][0] if source.get("scenes") else None
        if first_scene is not None:
            first_output = audio_root / f"{first_scene['id']}.wav"
            if first_output.is_file() and voice_config.provider == "omnivoice" and not voice_config.reference_audio:
                voice_anchor = first_output
                voice_anchor_text = str(first_scene.get("narration") or "")
        for index, item in enumerate(source["scenes"], 1):
            scene_id = str(item["id"])
            if included_scene_ids is not None and scene_id not in included_scene_ids:
                if scene_id not in existing_scenes:
                    raise ValueError(f"Cannot skip unknown scene {scene_id} during narration preparation.")
                scenes.append(dict(existing_scenes[scene_id]))
                continue
            selected_index += 1
            if on_scene:
                on_scene(selected_index, selected_total, scene_id)
            output = audio_root / f"{scene_id}.wav"
            synthesis_result = None
            generation_started = time.perf_counter()
            scene_voice_config = voice_config
            if (
                voice_anchor is not None
                and voice_config.provider == "omnivoice"
                and not voice_config.reference_audio
                and str(item.get("id")) != str(first_scene.get("id"))
            ):
                scene_voice_config = replace(
                    voice_config,
                    mode="voice_clone",
                    reference_audio=voice_anchor,
                    options={
                        **voice_config.options,
                        "reference_text": voice_anchor_text,
                        "automatic_voice_anchor": True,
                    },
                )
            if synthesize or not output.is_file():
                synthesis_result = voice_service.synthesize(str(item["narration"]), scene_voice_config, output)
            generation_seconds = round(time.perf_counter() - generation_started, 3) if synthesis_result else 0.0
            if (
                voice_anchor is None
                and voice_config.provider == "omnivoice"
                and not voice_config.reference_audio
                and str(item.get("id")) == str(first_scene.get("id"))
                and output.is_file()
            ):
                voice_anchor = output
                voice_anchor_text = str(item.get("narration") or "")
            duration = self._audio_duration(output)
            _, sample_rate = wav_metadata(output)
            phrases = self._phrases(str(item["narration"]))
            narration_target = duration + post_roll
            source_audio_duration = 0.0
            try:
                metadata = source_store.load_metadata(scene_id)
            except (ValueError, KeyError):
                # Legacy narration-only projects may not have imported source
                # metadata; in that case narration remains the timing master.
                metadata = {}
            for version in metadata.get("versions", []):
                if version.get("status") != "approved":
                    continue
                policy = version.get("source_audio") or {}
                if not policy.get("enabled") or policy.get("mode") == "mute":
                    continue
                probe = version.get("probe") or {}
                source_audio_duration = max(
                    source_audio_duration,
                    float(probe.get("audio_duration") or (probe.get("duration") if probe.get("has_audio") else 0) or 0),
                )
            scene_target = max(narration_target, source_audio_duration)
            scene_frames = math.ceil(scene_target * fps) + pre_roll_frames
            scene = dict(existing_scenes.get(scene_id, {}))
            scene.update({
                "id": scene_id,
                "index": index,
                "durationInFrames": scene_frames,
                "narrationOffsetFrames": pre_roll_frames,
                "narration": item["narration"],
                "intent": item.get("intent", ""),
                "narrationAudio": f"{'voice/narration' if is_desktop_project else 'audio'}/{scene_id}.wav",
                "subtitle": self._subtitle_timing(phrases, duration, fps, pre_roll_frames),
            })
            scene.setdefault("approved", False)
            scene.setdefault("layout", "full_bleed")
            scene.setdefault("mascotPose", "idle")
            scene.setdefault("animation", {"type": "slow_push_in"})
            scene.setdefault("focalPoint", {"x": 0.5, "y": 0.5})
            scene.setdefault("transition", transitions[(index - 1) % len(transitions)])
            scenes.append(scene)
            report.append({
                "scene_id": scene_id,
                "narration_duration": round(duration, 3),
                "voice_duration": round(duration, 3),
                "target_duration": round(scene_frames / fps, 3),
                "timeline_duration": round(scene_frames / fps, 3),
                "source_audio_duration": round(source_audio_duration, 3),
                "timing_target": "source_audio" if source_audio_duration > narration_target else "narration",
                "pre_roll_seconds": round(pre_roll_frames / fps, 3),
                "post_roll_seconds": round((scene_frames - pre_roll_frames) / fps - duration, 3),
                "voice_speed": scene_voice_config.speed,
                "voice_num_step": int(scene_voice_config.options["num_step"]),
                "voice_speed_fit": "forbidden",
                "voice_speed_fit_code": VOICE_SPEED_FIT_FORBIDDEN,
                "generation_seconds": generation_seconds,
                "subtitle_phrases": len(phrases),
                "voice": synthesis_result.to_dict() if synthesis_result else {
                    "audio_file": str(output),
                    "provider": scene_voice_config.provider,
                    "voice_id": voice_config.voice_id,
                    "language": voice_config.language,
                    "duration": round(duration, 3),
                    "sample_rate": sample_rate,
                    "timing": None,
                    "cache_hit": True,
                },
            })
            if on_scene:
                on_scene(selected_index + 1, selected_total, scene_id)
        project = dict(existing_project)
        project.update({
            "name": source.get("title", project.get("name", self.project_name)),
            "fps": fps,
            "width": project.get("width", 1080),
            "height": project.get("height", 1920),
            "style": project.get("style", "cartoon_explainer"),
            "scenes": scenes,
        })
        project.setdefault("sourceVideoSettings", {
                "auto_approve_latest": False,
                "source_audio_default": {
                    "mode": "background", "volume": 0.30, "duck_under_narration": True,
                    "fade_in": 0.15, "fade_out": 0.20,
                },
            })
        remotion_path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Scene metadata remains authoritative for imported/approved source clips.
        SceneVideoStore(self.repo_root, self.project_name).sync_all_to_remotion(recompute_timing=True)
        projected = json.loads(remotion_path.read_text(encoding="utf-8"))
        projected_scenes = {str(item["id"]): item for item in projected.get("scenes", [])}
        for item in report:
            visual = projected_scenes.get(item["scene_id"], {})
            source_video = next((entry for entry in visual.get("videoSources", []) if entry.get("review") == "approved"), None)
            if source_video is None:
                item.update({"source_duration": None, "visual_playback_rate": None, "hold_duration": 0.0})
                continue
            source_duration = float(source_video.get("duration") or 0)
            trim = source_video.get("trim") or {}
            trimmed_duration = max(0.0, float(trim.get("end") or source_duration) - float(trim.get("start") or 0))
            visual_speed = float(source_video.get("playbackRate") or 1.0)
            visible_duration = trimmed_duration / visual_speed
            item.update({
                "source_duration": round(source_duration, 3),
                "source_trimmed_duration": round(trimmed_duration, 3),
                "visual_playback_rate": round(visual_speed, 4),
                "hold_duration": round(max(0.0, item["target_duration"] - visible_duration), 3) if source_video.get("holdLastFrame") else 0.0,
            })
        result = {
            "project": self.project_name,
            "voice_provider": voice_config.provider,
            "voice_model": voice_config.options.get("engine") or "k2-fsa/OmniVoice",
            "voice_num_step": int(voice_config.options["num_step"]),
            "voice_speed": voice_config.speed,
            "voice_seed": None,
            "session_mode": "sequential_warm_worker" if synthesize else "reuse_existing_audio",
            "timing_authority": "narration_audio",
            "voice_speed_fit": "forbidden",
            "voice_speed_fit_code": VOICE_SPEED_FIT_FORBIDDEN,
            "voice_backend": "provider-neutral voice service; OmniVoice remains the default",
            "voice_warning": voice_service.last_warning,
            "total_narration_duration": round(sum(item["narration_duration"] for item in report), 3),
            "total_timeline_duration": round(sum(item["timeline_duration"] for item in report), 3),
            "scenes": report,
            "remotion_path": str(remotion_path),
        }
        report_path = self.project_root / "narration-report.json"
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result
