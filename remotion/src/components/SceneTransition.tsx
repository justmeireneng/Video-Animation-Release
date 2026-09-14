import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {transitionProgress} from '../animations/transitions';
import type {Scene} from '../types/scene';

export const SceneTransition = ({type}: {type: Scene['transition']}) => {
  const frame = useCurrentFrame();
  if (type === 'none') return null;
  const progress = transitionProgress(frame);
  if (type === 'crossfade') {
    return <AbsoluteFill style={{background: '#142235', opacity: interpolate(progress, [0, 1], [1, 0]), pointerEvents: 'none'}} />;
  }
  if (type === 'wipe_reveal') {
    return <AbsoluteFill style={{background: '#ffbd45', clipPath: `inset(0 ${progress * 100}% 0 0)`, pointerEvents: 'none'}} />;
  }
  if (type === 'paper') {
    return <AbsoluteFill style={{background: '#f2eadc', clipPath: `polygon(0 0, ${progress * 112}% 0, ${Math.max(0, progress * 112 - 12)}% 100%, 0 100%)`, opacity: 1 - progress, pointerEvents: 'none'}} />;
  }
  return <AbsoluteFill style={{background: 'linear-gradient(90deg, #66dcf2, #ffbd45)', transform: `translateX(${interpolate(progress, [0, 1], [0, 110])}%)`, pointerEvents: 'none'}} />;
};
