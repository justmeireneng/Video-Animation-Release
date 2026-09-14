import {interpolate} from 'remotion';

export const getParallaxTransform = (
  frame: number,
  durationInFrames: number,
  depth: 'background' | 'midground' | 'foreground',
): string => {
  const amount = depth === 'background' ? 1.2 : depth === 'midground' ? 2.8 : 5;
  const scale = depth === 'background' ? 1.04 : depth === 'midground' ? 1.07 : 1.1;
  const x = interpolate(frame, [0, Math.max(1, durationInFrames - 1)], [-amount, amount], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return `translateX(${x}%) scale(${scale})`;
};
