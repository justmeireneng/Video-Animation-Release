import {Audio} from '@remotion/media';
import {AbsoluteFill, Sequence, staticFile} from 'remotion';
import {Background} from '../components/Background';
import {Mascot} from '../components/Mascot';
import {SafeZone} from '../components/SafeZone';
import {SceneVisual} from '../components/SceneVisual';
import {SceneSourceBadge} from '../components/SceneSourceBadge';
import {SceneTransition} from '../components/SceneTransition';
import {Subtitle} from '../components/Subtitle';
import {CenterMascotCorner} from '../layouts/CenterMascotCorner';
import {ComparisonSplit} from '../layouts/ComparisonSplit';
import {FullImageOverlay} from '../layouts/FullImageOverlay';
import {ImageLeftMascotRight} from '../layouts/ImageLeftMascotRight';
import type {RemotionProject, Scene} from '../types/scene';

type Props = {project: RemotionProject; projectSlug: string; scene: Scene};

export const SceneComposition = ({project, projectSlug, scene}: Props) => {
  const fullBleed = scene.layout === 'full_bleed';
  const image = <SceneVisual scene={scene} projectSlug={projectSlug} fullBleed={fullBleed} />;
  const compactMascot = scene.layout !== 'image_left_mascot_right';
  const mascot = <Mascot projectSlug={projectSlug} mascot={project.mascot} pose={scene.mascotPose} compact={compactMascot} />;
  const layout = fullBleed
    ? image
    : scene.layout === 'image_center_mascot_corner'
    ? <CenterMascotCorner image={image} mascot={mascot} />
    : scene.layout === 'full_image_mascot_overlay'
      ? <FullImageOverlay image={image} mascot={mascot} />
      : scene.layout === 'comparison_split'
        ? <ComparisonSplit image={image} mascot={mascot} />
        : <ImageLeftMascotRight image={image} mascot={mascot} />;

  return (
    <AbsoluteFill style={{fontFamily: '"Be Vietnam Pro", sans-serif'}}>
      <Background />
      {layout}
      <Sequence from={scene.narrationOffsetFrames ?? 0}>
        <Audio src={staticFile(`${projectSlug}/${scene.narrationAudio}`)} volume={1} />
      </Sequence>
      {scene.sfx?.map((sfx, index) => (
        <Sequence key={`${sfx.src}-${index}`} from={sfx.startFrame ?? 0} premountFor={15}>
          <Audio src={staticFile(`${projectSlug}/${sfx.src}`)} volume={sfx.volume ?? 0.16} />
        </Sequence>
      ))}
      <Subtitle phrases={scene.subtitle} offsetY={scene.subtitleOffsetY} />
      <SceneSourceBadge scene={scene} />
      <SafeZone />
      <SceneTransition type={scene.transition} />
    </AbsoluteFill>
  );
};
