from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any

from src.providers.base import wav_metadata
from src.services.voice_service import VoiceConfig, VoiceService
from src.video.scene_source_manager import SceneVideoStore, find_ffprobe


class NarrationTimelineService:
    """Build narration audio and phrase subtitles without changing storyboard source files."""

    def __init__(self, repo_root: Path | str, project_name: str):
        self.repo_root = Path(repo_root).resolve()
        self.project_name = project_name
        self.project_root = self.repo_root / "projects" / project_name
        self.source_path = self.project_root / "narration.json"
        if not self.source_path.is_file():
            raise FileNotFoundError(f"Narration source not found: {self.source_path}")

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
    def _subtitle_timing(phrases: list[str], duration: float, fps: int) -> list[dict[str, Any]]:
        total_words = sum(len(phrase.split()) for phrase in phrases)
        frame_end = max(1, round(duration * fps))
        cursor = 0
        result: list[dict[str, Any]] = []
        consumed = 0
        for index, phrase in enumerate(phrases):
            consumed += len(phrase.split())
            end = frame_end if index == len(phrases) - 1 else round(frame_end * consumed / total_words)
            end = max(cursor + 1, end)
            result.append({"startFrame": cursor, "endFrame": end, "text": phrase})
            cursor = end
        return result

    def prepare(self, *, synthesize: bool = True) -> dict[str, Any]:
        source = json.loads(self.source_path.read_text(encoding="utf-8"))
        remotion_path = self.project_root / "remotion.json"
        existing_project = json.loads(remotion_path.read_text(encoding="utf-8")) if remotion_path.is_file() else {}
        existing_scenes = {str(item.get("id")): item for item in existing_project.get("scenes", [])}
        fps = 30
        pause = float(source.get("scene_pause_seconds", 0.35))
        audio_root = self.project_root / "audio"
        audio_root.mkdir(parents=True, exist_ok=True)
        voice_config = VoiceConfig.from_project(source)
        voice_service = VoiceService(self.project_root)
        scenes: list[dict[str, Any]] = []
        report: list[dict[str, Any]] = []
        transitions = ["crossfade", "soft_slide", "crossfade", "paper"]
        for index, item in enumerate(source["scenes"], 1):
            scene_id = str(item["id"])
            output = audio_root / f"{scene_id}.wav"
            synthesis_result = None
            if synthesize or not output.is_file():
                synthesis_result = voice_service.synthesize(str(item["narration"]), voice_config, output)
            duration = self._audio_duration(output)
            _, sample_rate = wav_metadata(output)
            phrases = self._phrases(str(item["narration"]))
            scene_frames = math.ceil((duration + pause) * fps)
            scene = dict(existing_scenes.get(scene_id, {}))
            scene.update({
                "id": scene_id,
                "index": index,
                "durationInFrames": scene_frames,
                "narration": item["narration"],
                "intent": item.get("intent", ""),
                "narrationAudio": f"audio/{scene_id}.wav",
                "subtitle": self._subtitle_timing(phrases, duration, fps),
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
                "timeline_duration": round(scene_frames / fps, 3),
                "subtitle_phrases": len(phrases),
                "voice": synthesis_result.to_dict() if synthesis_result else {
                    "audio_file": str(output),
                    "provider": voice_config.provider,
                    "voice_id": voice_config.voice_id,
                    "language": voice_config.language,
                    "duration": round(duration, 3),
                    "sample_rate": sample_rate,
                    "timing": None,
                    "cache_hit": True,
                },
            })
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
        SceneVideoStore(self.repo_root, self.project_name).sync_all_to_remotion()
        result = {
            "project": self.project_name,
            "voice_provider": voice_config.provider,
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
