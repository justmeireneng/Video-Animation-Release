#!/usr/bin/env python3
"""
Base Abstraction Layer for AI Video Generator Providers.
Ensures zero vendor lock-in across Image, Video, Voice, and Compositor engines.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import wave

@dataclass
class ImageGenerationRequest:
    prompt: str
    negative_prompt: str = ""
    aspect_ratio: str = "9:16"
    resolution: tuple[int, int] = (1080, 1920)
    reference_images: list[Path | str] = field(default_factory=list)
    output_path: Path | str = "output.png"
    extra_params: dict[str, Any] = field(default_factory=dict)

class ImageProvider(ABC):
    @abstractmethod
    def generate_image(self, request: ImageGenerationRequest) -> Path:
        pass

@dataclass
class VideoGenerationRequest:
    image_path: Path | str
    motion_prompt: str = ""
    motion_type: str = "push_in"
    duration_s: float = 6.0
    fps: int = 24
    resolution: tuple[int, int] = (1080, 1920)
    output_path: Path | str = "clip.mp4"
    extra_params: dict[str, Any] = field(default_factory=dict)

class VideoProvider(ABC):
    @abstractmethod
    def animate_image(self, request: VideoGenerationRequest) -> Path:
        pass


@dataclass
class SceneVideoGenerationRequest:
    scene_id: str
    prompt: str
    reference_images: list[Path | str] = field(default_factory=list)
    duration_s: float = 6.0
    aspect_ratio: str = "9:16"
    output_path: Path | str = "clip.mp4"
    motion_prompt: str = ""
    extra_params: dict[str, Any] = field(default_factory=dict)


class SceneVideoProvider(ABC):
    """Vendor-neutral interface for scene-level source-video generation."""

    @abstractmethod
    def generate_scene_video(self, request: SceneVideoGenerationRequest) -> Path:
        pass

@dataclass
class VoiceGenerationRequest:
    text: str
    voice_id: str = "default"
    language: str = "vi"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    output_path: Path | str = "narration.wav"
    ref_audio: Path | str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceSynthesisResult:
    """Provider-neutral voice result consumed by narration and future UI code."""

    audio_file: Path | str
    provider: str
    voice_id: str
    language: str
    duration: float = 0.0
    sample_rate: int = 0
    timing: list[dict[str, Any]] | None = None
    engine: str | None = None
    cache_hit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "audio_file": str(self.audio_file),
            "provider": self.provider,
            "voice_id": self.voice_id,
            "language": self.language,
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "timing": self.timing,
            "engine": self.engine,
            "cache_hit": self.cache_hit,
        }


def wav_metadata(path: Path | str) -> tuple[float, int]:
    """Read duration/sample rate without adding an audio dependency."""

    try:
        with wave.open(str(path), "rb") as audio:
            sample_rate = audio.getframerate()
            duration = audio.getnframes() / sample_rate if sample_rate else 0.0
            return duration, sample_rate
    except (OSError, EOFError, wave.Error):
        return 0.0, 0

class VoiceProvider(ABC):
    provider_id = "unknown"
    display_name = "Unknown voice provider"

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def list_voices(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def synthesize(self, request: VoiceGenerationRequest) -> VoiceSynthesisResult:
        pass

    def generate_voice(self, request: VoiceGenerationRequest) -> Path:
        return Path(self.synthesize(request).audio_file)

    def generate_preview(self, request: VoiceGenerationRequest) -> VoiceSynthesisResult:
        return self.synthesize(request)

@dataclass
class CompositionRequest:
    video_clips: list[Path | str]
    narration_audio: Path | str
    sfx_audio: Path | str | None = None
    bgm_audio: Path | str | None = None
    subtitle_ass: Path | str | None = None
    fonts_dir: Path | str | None = None
    output_path: Path | str = "final_video.mp4"
    crf: int = 24
    fps: int = 24

class CompositorProvider(ABC):
    @abstractmethod
    def compose(self, request: CompositionRequest) -> Path:
        pass
