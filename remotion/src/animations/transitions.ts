import {Easing, interpolate} from 'remotion';

export const transitionProgress = (frame: number, duration = 18): number =>
  interpolate(frame, [0, duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
