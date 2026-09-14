#!/usr/bin/env python3
"""Vendor-neutral imported scene-video provider; Flow generation stays external."""
from __future__ import annotations

import shutil
from pathlib import Path

from ..base import SceneVideoGenerationRequest, SceneVideoProvider


class ExistingVideoProvider(SceneVideoProvider):
    provider_id = "existing_video"

    def generate_scene_video(self, request: SceneVideoGenerationRequest) -> Path:
        source = request.extra_params.get("source_file")
        if not source:
            raise ValueError("ExistingVideoProvider requires extra_params['source_file'].")
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        output = Path(request.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        if source_path.resolve() != output.resolve():
            shutil.copy2(source_path, output)
        return output
