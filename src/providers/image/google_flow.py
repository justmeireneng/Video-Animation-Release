#!/usr/bin/env python3
import json
import shutil
from pathlib import Path
from ..base import ImageProvider, ImageGenerationRequest

class GoogleFlowImageProvider(ImageProvider):
    def __init__(self, output_package_dir: Path | str = "flow_package"):
        self.package_dir = Path(output_package_dir)

    def generate_image(self, request: ImageGenerationRequest) -> Path:
        out_p = Path(request.output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        # Package prompt and references for generation
        pkg_scene = self.package_dir / out_p.stem
        pkg_scene.mkdir(parents=True, exist_ok=True)
        (pkg_scene / "prompt.txt").write_text(request.prompt, encoding="utf-8")
        if request.reference_images:
            ref_dir = pkg_scene / "references"
            ref_dir.mkdir(parents=True, exist_ok=True)
            for idx, ref in enumerate(request.reference_images):
                p_ref = Path(ref)
                if p_ref.exists():
                    shutil.copy2(p_ref, ref_dir / f"ref_{idx:02d}{p_ref.suffix}")
        return out_p
