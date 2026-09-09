#!/usr/bin/env python3
import subprocess
from pathlib import Path
from ..base import CompositorProvider, CompositionRequest

class FFmpegCompositorProvider(CompositorProvider):
    def compose(self, request: CompositionRequest) -> Path:
        out_p = Path(request.output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        # 1. Build concat file
        concat_txt = out_p.parent / "concat_list.txt"
        lines = [f"file '{Path(c).resolve().as_posix()}'" for c in request.video_clips]
        concat_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
        
        raw_concat = out_p.parent / "raw_concat.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            str(raw_concat)
        ], check=True)

        # 2. Final mux with audio & subtitles
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(raw_concat),
            "-i", str(Path(request.narration_audio).resolve()),
            "-c:v", "libx264", "-preset", "medium", "-crf", str(request.crf),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", "-shortest", str(out_p)
        ]
        if request.subtitle_ass and Path(request.subtitle_ass).exists():
            sub_p = Path(request.subtitle_ass).resolve()
            cmd.insert(4, "-vf")
            cmd.insert(5, f"ass='{sub_p.as_posix()}'")

        subprocess.run(cmd, check=True)
        return out_p
