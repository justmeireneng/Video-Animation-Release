import {Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {entrance} from '../animations/entrances';
import type {MascotPose, RemotionProject} from '../types/scene';

type Props = {
  projectSlug: string;
  mascot: RemotionProject['mascot'];
  pose: MascotPose;
  compact?: boolean;
};

export const Mascot = ({projectSlug, mascot, pose, compact = false}: Props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const bob = Math.sin((frame / fps) * Math.PI * 2 * 0.55) * 5;
  const breathe = 1 + Math.sin((frame / fps) * Math.PI * 2 * 0.28) * 0.012;
  const talk = pose === 'talking' ? Math.sin((frame / fps) * Math.PI * 8) * 2 : 0;
  const enter = entrance(frame, fps, 3);
  const flip = pose === 'point_left' ? -1 : 1;
  const tilt = pose === 'thinking' ? -2.5 : pose === 'surprised' ? 1.5 : 0;
  const width = compact ? 250 : 360;
  const height = compact ? 320 : 470;
  const resolved = mascot[pose] ?? mascot.idle;

  return (
    <div style={{width, height, filter: 'drop-shadow(0 24px 25px rgba(4,13,24,0.35))', ...enter}}>
      <div
        style={{
          width: '100%',
          height: '100%',
          overflow: 'hidden',
          borderRadius: '46% 46% 34% 34%',
          border: '8px solid rgba(255,255,255,0.92)',
          background: '#222930',
          transform: `translateY(${bob + talk}px) rotate(${tilt}deg) scale(${breathe}) scaleX(${flip})`,
        }}
      >
        <Img
          src={staticFile(`${projectSlug}/${resolved}`)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            objectPosition: 'center 44%',
            transform: `scale(${interpolate(frame, [0, 20], [1.04, 1], {extrapolateRight: 'clamp'})})`,
          }}
        />
      </div>
      <div style={{marginTop: -32, marginLeft: 24, display: 'inline-block', padding: '10px 20px', borderRadius: 999, background: '#142235', color: '#fff', font: '700 24px "Be Vietnam Pro"', textTransform: 'uppercase', letterSpacing: 1}}>
        {pose.replace('_', ' ')}
      </div>
    </div>
  );
};
