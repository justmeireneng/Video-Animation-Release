#!/usr/bin/env python3
"""
Cinematic 2.5D Image-to-Video Motion Engine.
Transforms static 1080x1920 images into cinematic explainer video clips (Google Flow aesthetic)
with true 2.5D depth parallax, 3D camera dynamics, volumetric light sweeps, atmospheric particles,
and kinetic tech UI accents without requiring heavy discrete GPU hardware.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class MotionType(str, Enum):
    PUSH_IN = "push_in"           # Smooth focal push-in with foreground expansion
    ORBIT_DRIFT = "orbit_drift"   # Subtle rotational yaw and diagonal drift
    PAN_HORIZONTAL = "pan_horiz"  # Lateral tracking shot with depth parallax
    CRANE_UP = "crane_up"         # Cinematic rising camera revealing horizon
    PULSE_ZOOM = "pulse_zoom"     # Rhythmic subtle breath zoom


@dataclass
class MotionConfig:
    motion_type: MotionType = MotionType.PUSH_IN
    duration_s: float = 6.0
    fps: int = 30
    zoom_range: tuple[float, float] = (1.0, 1.12)
    pan_x: float = 0.0            # Normalized -1.0 to 1.0
    pan_y: float = -0.04          # Slight upward/downward drift
    rotation_deg: float = 0.8     # Subtle roll
    light_sweep: bool = True
    particles: bool = True
    ui_accent: str = "none"       # 'none', 'code_stream', 'neural_pulse', 'tech_grid', 'data_nodes'


class CinematicMotionEngine:
    """
    Renders high-fidelity 1080x1920 video clips from a single master image.
    """

    def __init__(self, target_w: int = 1080, target_h: int = 1920):
        self.w = target_w
        self.h = target_h

    def _estimate_depth_map(self, img_bgr: np.ndarray) -> np.ndarray:
        """
        Synthesizes a 2.5D depth map Z(x, y) in [0.1, 1.0] using multi-scale luminance,
        edge saliency, and radial vignetting (center/subject is closer, edges farther).
        """
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

        # 1. Base radial focal plane (center is closer, z smaller)
        cy, cx = self.h * 0.45, self.w * 0.50
        y_indices, x_indices = np.indices((self.h, self.w))
        dist_from_focal = np.sqrt(((x_indices - cx) / self.w) ** 2 + ((y_indices - cy) / self.h) ** 2)
        radial_depth = np.clip(dist_from_focal * 1.2, 0.0, 1.0)

        # 2. Luminance depth (highlights pop forward)
        blurred_lum = cv2.GaussianBlur(gray, (51, 51), 0)
        lum_depth = 1.0 - blurred_lum

        # 3. Vertical depth gradient (ground plane perspective)
        vert_grad = (y_indices / self.h) * 0.4

        # Combine into normalized depth map
        depth = 0.4 * radial_depth + 0.4 * lum_depth + 0.2 * vert_grad
        depth = cv2.GaussianBlur(depth, (31, 31), 0)
        depth = np.clip(depth, 0.15, 1.0).astype(np.float32)
        return depth

    def render_clip(
        self,
        image_path: Path | str,
        output_mp4: Path | str,
        config: MotionConfig,
    ) -> Path:
        out_p = Path(output_mp4)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        raw_bytes = np.fromfile(str(image_path), dtype=np.uint8)
        src_img = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
        if src_img is None:
            raise ValueError(f"Không thể đọc ảnh: {image_path}")

        if (src_img.shape[1], src_img.shape[0]) != (self.w, self.h):
            src_img = cv2.resize(src_img, (self.w, self.h), interpolation=cv2.INTER_CUBIC)

        depth_map = self._estimate_depth_map(src_img)

        # Pre-generate 3D particles
        num_particles = 60 if config.particles else 0
        particles = []
        for _ in range(num_particles):
            particles.append({
                "x": random.uniform(0, self.w),
                "y": random.uniform(0, self.h),
                "z": random.uniform(0.2, 1.0),
                "radius": random.uniform(1.5, 3.5),
                "vx": random.uniform(-15.0, 15.0),
                "vy": random.uniform(-25.0, -8.0),
                "alpha": random.uniform(0.25, 0.65),
                "color": random.choice([(255, 230, 180), (180, 220, 255), (255, 255, 255)]),
            })

        total_frames = int(round(config.duration_s * config.fps))
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out_p), fourcc, config.fps, (self.w, self.h))

        cx, cy = self.w / 2.0, self.h / 2.0
        x_mesh, y_mesh = np.meshgrid(np.arange(self.w, dtype=np.float32), np.arange(self.h, dtype=np.float32))
        qw, qh = self.w // 4, self.h // 4
        x_q, y_q = np.meshgrid(np.arange(qw, dtype=np.float32), np.arange(qh, dtype=np.float32))

        for f in range(total_frames):
            # Smooth cubic ease-in-out progress t in [0.0, 1.0]
            t_linear = f / max(1, total_frames - 1)
            t = 3 * (t_linear ** 2) - 2 * (t_linear ** 3)

            # Compute transformation parameters
            z_min, z_max = config.zoom_range
            curr_zoom = z_min + (z_max - z_min) * t
            curr_pan_x = config.pan_x * self.w * t
            curr_pan_y = config.pan_y * self.h * t
            curr_rot = config.rotation_deg * math.sin(t * math.pi)

            # 2.5D Parallax mapping with cv2.remap
            # Near elements (depth near 0.15) shift and zoom more than far elements (depth near 1.0)
            parallax_scale = 1.0 + (curr_zoom - 1.0) * (1.35 - depth_map * 0.7)
            inv_scale = 1.0 / np.maximum(parallax_scale, 0.01)

            rot_rad = math.radians(curr_rot)
            cos_r = math.cos(rot_rad)
            sin_r = math.sin(rot_rad)

            # Center coordinates
            dx = (x_mesh - cx) - curr_pan_x * (1.3 - depth_map * 0.6)
            dy = (y_mesh - cy) - curr_pan_y * (1.3 - depth_map * 0.6)

            # Rotate and scale back into source image space
            src_x = (dx * cos_r - dy * sin_r) * inv_scale + cx
            src_y = (dx * sin_r + dy * cos_r) * inv_scale + cy

            map_x = src_x.astype(np.float32)
            map_y = src_y.astype(np.float32)

            warped = cv2.remap(src_img, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

            # 1. Volumetric Light Sweep (Anamorphic highlight traveling diagonally)
            if config.light_sweep:
                sweep_x = -qw * 0.3 + (qw * 1.6) * t_linear
                band_w = qw * 0.45
                center_mesh = sweep_x + (y_q - qh / 2.0) * 0.35
                dist_from_center = np.abs(x_q - center_mesh)
                in_band = dist_from_center < (band_w / 2.0)

                light_mask_q = np.zeros((qh, qw), dtype=np.float32)
                light_mask_q[in_band] = 0.5 * (1.0 + np.cos(dist_from_center[in_band] * (math.pi / (band_w / 2.0))))
                
                # Resize light mask to full resolution smoothly
                lm_full = cv2.resize((light_mask_q * 42.0).astype(np.uint8), (self.w, self.h), interpolation=cv2.INTER_LINEAR)
                # Cyan/amber cool daylight tint
                light_bgr = cv2.merge([
                    (lm_full * 1.25).clip(0, 255).astype(np.uint8),
                    (lm_full * 1.10).clip(0, 255).astype(np.uint8),
                    lm_full
                ])
                frame = cv2.add(warped, light_bgr)
            else:
                frame = warped

            # 2. Kinetic UI Overlays (Google Flow style tech accents)
            if config.ui_accent == "neural_pulse":
                # Concentric expanding pulse rings from focal center
                pulse_r = int(((t_linear * 3.0) % 1.0) * self.w * 0.6)
                alpha_ring = max(0.0, 1.0 - (((t_linear * 3.0) % 1.0))) * 0.4
                overlay = frame.copy()
                cv2.circle(overlay, (int(cx), int(cy)), pulse_r, (255, 200, 80), 2, cv2.LINE_AA)
                cv2.circle(overlay, (int(cx), int(cy)), max(1, pulse_r - 20), (80, 220, 255), 1, cv2.LINE_AA)
                cv2.addWeighted(overlay, alpha_ring, frame, 1.0 - alpha_ring, 0, frame)

            elif config.ui_accent == "code_stream":
                # Subtle vertical terminal data streams on side margins
                overlay = frame.copy()
                bar_y = int((t_linear * 4.0 % 1.0) * self.h)
                cv2.line(overlay, (60, bar_y), (60, min(self.h, bar_y + 120)), (100, 255, 120), 2, cv2.LINE_AA)
                cv2.line(overlay, (self.w - 60, (self.h - bar_y)), (self.w - 60, min(self.h, self.h - bar_y + 120)), (100, 255, 120), 2, cv2.LINE_AA)
                cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)

            elif config.ui_accent == "tech_grid":
                # Subtle crosshair corners
                overlay = frame.copy()
                for c_px, c_py in [(80, 180), (self.w - 80, 180), (80, self.h - 320), (self.w - 80, self.h - 320)]:
                    cv2.drawMarker(overlay, (c_px, c_py), (255, 255, 255), cv2.MARKER_CROSS, 24, 1)
                cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

            # 3. Floating 3D Particles
            if config.particles and particles:
                for p in particles:
                    px = (p["x"] + p["vx"] * t_linear * config.duration_s) % self.w
                    py = (p["y"] + p["vy"] * t_linear * config.duration_s) % self.h
                    # Apparent size scaled by depth
                    rad = int(round(p["radius"] * (1.4 - p["z"] * 0.5)))
                    alpha = p["alpha"] * (0.8 + 0.2 * math.sin(f * 0.15))
                    cv2.circle(frame, (int(px), int(py)), rad, p["color"], -1, cv2.LINE_AA)

            writer.write(frame)

        writer.release()
        return out_p
