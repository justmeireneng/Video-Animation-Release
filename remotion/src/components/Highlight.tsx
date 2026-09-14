import {useCurrentFrame, useVideoConfig} from 'remotion';
import {emphasisPulse, revealProgress} from '../animations/emphasis';
import type {FocalPoint} from '../types/scene';

export const Highlight = ({focalPoint, active}: {focalPoint: FocalPoint; active: boolean}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  if (!active) return null;
  const reveal = revealProgress(frame, durationInFrames);
  return (
    <div
      style={{
        position: 'absolute',
        left: `${focalPoint.x * 100}%`,
        top: `${focalPoint.y * 100}%`,
        width: 150,
        height: 150,
        marginLeft: -75,
        marginTop: -75,
        border: '9px solid #ffbd45',
        borderRadius: '50%',
        boxShadow: '0 0 0 12px rgba(255,189,69,0.2)',
        opacity: reveal,
        transform: `scale(${emphasisPulse(frame, fps) * reveal})`,
      }}
    />
  );
};
