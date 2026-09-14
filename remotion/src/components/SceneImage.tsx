import {AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {getParallaxTransform} from '../animations/parallax';
import {getImageTransform} from '../animations/panZoom';
import {revealProgress} from '../animations/emphasis';
import type {Scene} from '../types/scene';
import {Highlight} from './Highlight';

type Props = {scene: Scene; projectSlug: string};

export const SceneImage = ({scene, projectSlug}: Props) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const asset = (path: string) => staticFile(`${projectSlug}/${path}`);
  const transform = getImageTransform({
    frame,
    durationInFrames,
    preset: scene.animation.type,
    focalPoint: scene.focalPoint,
    scaleFrom: scene.animation.scaleFrom,
    scaleTo: scene.animation.scaleTo,
  });
  const layers = scene.parallax;
  const completeParallax = layers?.background && layers.midground && layers.foreground;
  const reveal = revealProgress(frame, durationInFrames);

  if (!scene.approved || !scene.image) {
    return (
      <AbsoluteFill style={{borderRadius: 34, background: '#172131', color: '#dbeafe', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 38, fontWeight: 700}}>
        VISUAL PENDING REVIEW
      </AbsoluteFill>
    );
  }

  if (scene.animation.type === 'parallax' && completeParallax) {
    return (
      <AbsoluteFill style={{overflow: 'hidden', borderRadius: 34}}>
        {(['background', 'midground', 'foreground'] as const).map((depth) => (
          <Img
            key={depth}
            src={asset(layers[depth]!)}
            style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', transform: getParallaxTransform(frame, durationInFrames, depth)}}
          />
        ))}
      </AbsoluteFill>
    );
  }

  const clipPath = scene.animation.type === 'wipe_reveal'
    ? `inset(0 ${100 - reveal * 100}% 0 0 round 34px)`
    : undefined;
  const comparisonClip = scene.animation.type === 'comparison_reveal'
    ? `inset(0 ${100 - reveal * 100}% 0 0)`
    : undefined;

  return (
    <AbsoluteFill style={{overflow: 'hidden', borderRadius: 34, background: '#172131'}}>
      <Img
        src={asset(scene.image)}
        style={{width: '100%', height: '100%', objectFit: 'cover', clipPath, ...transform}}
      />
      {scene.comparisonImage ? (
        <Img
          src={asset(scene.comparisonImage)}
          style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', clipPath: comparisonClip, opacity: scene.animation.type === 'comparison_reveal' ? 1 : 0}}
        />
      ) : null}
      {scene.animation.type === 'sequential_blocks' || scene.animation.type === 'card_entrance' ? (
        <div style={{position: 'absolute', left: 34, right: 34, bottom: 42, display: 'flex', gap: 14}}>
          {[0, 1, 2].map((item) => {
            const visible = Math.max(0, Math.min(1, (frame - item * 12) / 18));
            return <div key={item} style={{height: 14, flex: 1, borderRadius: 20, background: item === 2 ? '#ffbd45' : '#66dcf2', opacity: visible, transform: `translateY(${(1 - visible) * 18}px)`}} />;
          })}
        </div>
      ) : null}
      <Highlight focalPoint={scene.focalPoint} active={scene.animation.type === 'highlight_object'} />
    </AbsoluteFill>
  );
};
