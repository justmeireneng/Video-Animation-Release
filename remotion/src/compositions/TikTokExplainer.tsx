import {Audio} from '@remotion/media';
import {AbsoluteFill, Series, staticFile} from 'remotion';
import type {ProjectLocator} from '../types/scene';
import {SceneComposition} from './SceneComposition';
import {BundledFonts} from '../components/BundledFonts';

export const TikTokExplainer = ({project, projectSlug}: ProjectLocator) => {
  if (!project) throw new Error('[Remotion project] calculateMetadata did not provide project data.');
  return (
    <AbsoluteFill style={{backgroundColor: '#142235'}}>
      <BundledFonts />
      {project.audio?.bgm ? <Audio src={staticFile(`${projectSlug}/${project.audio.bgm}`)} volume={project.audio.bgmVolume ?? 0.08} loop /> : null}
      <Series>
        {project.scenes.map((scene) => (
          <Series.Sequence key={scene.id} durationInFrames={scene.durationInFrames} name={`${scene.index}. ${scene.id}`} premountFor={30}>
            <SceneComposition project={project} projectSlug={projectSlug} scene={scene} />
          </Series.Sequence>
        ))}
      </Series>
    </AbsoluteFill>
  );
};
