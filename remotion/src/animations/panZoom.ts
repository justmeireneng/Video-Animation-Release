import {Easing, interpolate} from 'remotion';
import type {AnimationPreset, FocalPoint} from '../types/scene';

type TransformInput = {
  frame: number;
  durationInFrames: number;
  preset: AnimationPreset;
  focalPoint: FocalPoint;
  scaleFrom?: number;
  scaleTo?: number;
};

export const getImageTransform = ({
  frame,
  durationInFrames,
  preset,
  focalPoint,
  scaleFrom,
  scaleTo,
}: TransformInput): {transform: string; transformOrigin: string; opacity: number} => {
  const progress = interpolate(frame, [0, Math.max(1, durationInFrames - 1)], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });
  const origin = `${focalPoint.x * 100}% ${focalPoint.y * 100}%`;
  let scale = 1;
  let x = 0;
  let y = 0;

  switch (preset) {
    case 'slow_zoom_out':
      scale = (scaleFrom ?? 1.1) + ((scaleTo ?? 1) - (scaleFrom ?? 1.1)) * progress;
      break;
    case 'pan_left_to_right':
      scale = 1.08;
      x = -4 + 8 * progress;
      break;
    case 'pan_right_to_left':
      scale = 1.08;
      x = 4 - 8 * progress;
      break;
    case 'gentle_vertical_pan':
      scale = 1.07;
      y = 3 - 6 * progress;
      break;
    case 'focus_shift':
      scale = 1.03 + Math.sin(progress * Math.PI) * 0.05;
      x = (0.5 - focalPoint.x) * 8 * progress;
      y = (0.5 - focalPoint.y) * 8 * progress;
      break;
    case 'soft_slide':
      scale = 1.03;
      x = -3 + 3 * progress;
      break;
    default:
      scale = (scaleFrom ?? 1) + ((scaleTo ?? 1.08) - (scaleFrom ?? 1)) * progress;
  }

  const opacity = preset === 'crossfade' ? interpolate(frame, [0, 16], [0, 1], {extrapolateRight: 'clamp'}) : 1;
  return {transform: `translate(${x}%, ${y}%) scale(${scale})`, transformOrigin: origin, opacity};
};
