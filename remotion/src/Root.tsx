import type {CalculateMetadataFunction} from 'remotion';
import {Composition, staticFile} from 'remotion';
import {TikTokExplainer} from './compositions/TikTokExplainer';
import {getProjectDuration, loadProject, projectAssetPath, validateProjectAssets} from './loaders/projectLoader';
import type {ProjectLocator} from './types/scene';

const defaultProps: ProjectLocator = {
  projectSlug: 'Astra_AI_Explainer',
  configFile: 'remotion.json',
};

const calculateMetadata: CalculateMetadataFunction<ProjectLocator> = async ({props}) => {
  const project = await loadProject(props);
  await validateProjectAssets(project, async (asset) => {
    const response = await fetch(staticFile(projectAssetPath(props.projectSlug, asset)), {method: 'HEAD'});
    return response.ok;
  });
  return {
    durationInFrames: getProjectDuration(project),
    fps: project.fps,
    width: project.width,
    height: project.height,
    props: {...props, project},
  };
};

export const RemotionRoot = () => (
  <Composition
    id="TikTokExplainer"
    component={TikTokExplainer}
    durationInFrames={30}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={defaultProps}
    calculateMetadata={calculateMetadata}
  />
);
