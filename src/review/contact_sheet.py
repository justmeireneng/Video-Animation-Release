#!/usr/bin/env python3
from pathlib import Path
import cv2
import numpy as np

def generate_storyboard_contact_sheet(
    image_paths: list[Path | str],
    titles: list[str],
    output_path: Path | str,
    grid_cols: int = 4,
    grid_rows: int = 2
) -> Path:
    target_w, target_h = 480, 853
    header_h = 50
    cell_w, cell_h = target_w, target_h + header_h
    canvas = np.full((grid_rows * cell_h + 80, grid_cols * cell_w + 50, 3), (18, 16, 14), dtype=np.uint8)
    cv2.putText(canvas, 'STORYBOARD CONTACT SHEET', (40, 50), cv2.FONT_HERSHEY_DUPLEX, 1.1, (240, 220, 180), 2, cv2.LINE_AA)
    for idx, (p, title) in enumerate(zip(image_paths, titles)):
        r, c = idx // grid_cols, idx % grid_cols
        x, y = 25 + c * cell_w, 70 + r * cell_h
        cv2.rectangle(canvas, (x, y), (x + cell_w - 5, y + header_h), (28, 25, 22), -1)
        cv2.putText(canvas, title, (x + 10, y + 32), cv2.FONT_HERSHEY_DUPLEX, 0.48, (200, 220, 240), 1, cv2.LINE_AA)
        img = cv2.imread(str(p))
        if img is not None:
            thumb = cv2.resize(img, (target_w - 5, target_h), interpolation=cv2.INTER_AREA)
            canvas[y + header_h : y + header_h + target_h, x : x + target_w - 5] = thumb
        cv2.rectangle(canvas, (x, y), (x + cell_w - 5, y + cell_h), (80, 70, 60), 2)
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_p), canvas)
    return out_p
