import {interpolate, spring} from 'remotion';

export const entrance = (frame: number, fps: number, delay = 0) => {
  const local = Math.max(0, frame - delay);
  const progress = spring({frame: local, fps, config: {damping: 18, mass: 0.8, stiffness: 130}});
  return {
    opacity: interpolate(progress, [0, 1], [0, 1]),
    transform: `translateY(${interpolate(progress, [0, 1], [36, 0])}px) scale(${interpolate(progress, [0, 1], [0.96, 1])})`,
  };
};
