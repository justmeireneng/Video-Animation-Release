import {interpolate} from 'remotion';

export const emphasisPulse = (frame: number, fps: number): number => {
  const phase = (frame % Math.max(1, fps * 2)) / Math.max(1, fps * 2);
  return 1 + Math.sin(phase * Math.PI * 2) * 0.025;
};

export const revealProgress = (frame: number, durationInFrames: number): number =>
  interpolate(frame, [8, Math.min(durationInFrames - 1, 42)], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
