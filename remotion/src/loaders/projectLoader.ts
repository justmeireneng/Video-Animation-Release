import {staticFile} from 'remotion';
import {
  animationPresets,
  layouts,
  mascotPoses,
  type AnimationPreset,
  type MascotPose,
  type ProjectLocator,
  type RemotionProject,
  type Scene,
  type SceneVideoSource,
} from '../types/scene';

export const DEFAULT_ANIMATION: AnimationPreset = 'slow_push_in';

const required: (condition: unknown, message: string) => asserts condition = (condition, message) => {
  if (!condition) throw new Error(`[Remotion project] ${message}`);
};

const clamp01 = (value: unknown, fallback: number): number => {
  return typeof value === 'number' && Number.isFinite(value)
    ? Math.min(1, Math.max(0, value))
    : fallback;
};

export const normalizeProject = (input: unknown): RemotionProject => {
  required(input && typeof input === 'object', 'Project JSON must be an object.');
  const raw = input as Record<string, unknown>;
  required(typeof raw.name === 'string' && raw.name.length > 0, 'Missing project name.');
  required(Number.isInteger(raw.fps) && Number(raw.fps) > 0, 'fps must be a positive integer.');
  required(Number.isInteger(raw.width) && Number(raw.width) > 0, 'width must be a positive integer.');
  required(Number.isInteger(raw.height) && Number(raw.height) > 0, 'height must be a positive integer.');
  required(Array.isArray(raw.scenes) && raw.scenes.length > 0, 'At least one scene is required.');
  required(raw.mascot && typeof raw.mascot === 'object', 'Missing mascot asset map.');

  const mascotRaw = raw.mascot as Record<string, unknown>;
  required(typeof mascotRaw.idle === 'string' && mascotRaw.idle.length > 0, 'mascot.idle is required.');
  const mascot = Object.fromEntries(
    mascotPoses.map((pose) => [pose, typeof mascotRaw[pose] === 'string' ? mascotRaw[pose] : mascotRaw.idle]),
  ) as RemotionProject['mascot'];

  const scenes = (raw.scenes as Array<Record<string, unknown>>)
    .map((scene, sourceIndex): Scene => {
      required(typeof scene.id === 'string' && scene.id.length > 0, `Scene ${sourceIndex + 1}: missing id.`);
      required(Number.isInteger(scene.durationInFrames) && Number(scene.durationInFrames) > 0, `${scene.id}: invalid durationInFrames.`);
      required(typeof scene.narrationAudio === 'string' && scene.narrationAudio.length > 0, `${scene.id}: missing narrationAudio.`);

      const requestedAnimation = (scene.animation as {type?: string} | undefined)?.type;
      const animation = animationPresets.includes(requestedAnimation as AnimationPreset)
        ? (scene.animation as Scene['animation'])
        : {type: DEFAULT_ANIMATION};
      const requestedLayout = scene.layout;
      const layout = layouts.includes(requestedLayout as Scene['layout'])
        ? (requestedLayout as Scene['layout'])
        : 'image_left_mascot_right';
      const requestedPose = scene.mascotPose;
      const mascotPose = mascotPoses.includes(requestedPose as MascotPose)
        ? (requestedPose as MascotPose)
        : 'idle';
      const durationInFrames = Number(scene.durationInFrames);
      const subtitle = Array.isArray(scene.subtitle)
        ? (scene.subtitle as Scene['subtitle'])
            .filter((phrase) => phrase && typeof phrase.text === 'string')
            .map((phrase) => {
              const startFrame = Math.min(
                durationInFrames - 1,
                Math.max(0, Math.round(Number(phrase.startFrame) || 0)),
              );
              const requestedEnd = Math.round(Number(phrase.endFrame) || durationInFrames);
              return {
                ...phrase,
                startFrame,
                endFrame: Math.min(durationInFrames, Math.max(startFrame + 1, requestedEnd)),
              };
            })
        : [];

      return {
        ...(scene as unknown as Scene),
        index: Number.isInteger(scene.index) ? Number(scene.index) : sourceIndex + 1,
        durationInFrames,
        approved: scene.approved === true,
        image: typeof scene.image === 'string' ? scene.image : undefined,
        layout,
        mascotPose,
        animation,
        subtitle,
        focalPoint: {
          x: clamp01((scene.focalPoint as {x?: unknown} | undefined)?.x, 0.5),
          y: clamp01((scene.focalPoint as {y?: unknown} | undefined)?.y, 0.5),
        },
      };
    })
    .sort((a, b) => a.index - b.index);

  return {
    ...(raw as unknown as RemotionProject),
    fps: Number(raw.fps),
    width: Number(raw.width),
    height: Number(raw.height),
    style: 'cartoon_explainer',
    mascot,
    scenes,
  };
};

export const getProjectDuration = (project: RemotionProject): number =>
  project.scenes.reduce((sum, scene) => sum + scene.durationInFrames, 0);

export const projectAssetPath = (projectSlug: string, asset: string): string =>
  `${projectSlug}/${asset.replaceAll('\\', '/')}`;

const providerPriority = (provider: string): number => {
  const normalized = provider.toLowerCase();
  if (normalized.includes('google_flow') || normalized.includes('flow')) return 3;
  if (normalized.includes('generated')) return 2;
  return 1;
};

export const selectApprovedVideoSource = (scene: Scene): SceneVideoSource | undefined =>
  [...(scene.videoSources ?? [])]
    .filter((source) => source.review === 'approved')
    .sort((a, b) => providerPriority(b.provider) - providerPriority(a.provider) || b.version - a.version)[0];

export const getSceneSourceType = (scene: Scene): 'FLOW_VIDEO' | 'GENERATED_VIDEO' | 'STATIC_IMAGE' | 'PLACEHOLDER' => {
  const approvedVideo = selectApprovedVideoSource(scene);
  if (approvedVideo) return approvedVideo.provider.toLowerCase().includes('flow') ? 'FLOW_VIDEO' : 'GENERATED_VIDEO';
  if (scene.approved && scene.image) return 'STATIC_IMAGE';
  return 'PLACEHOLDER';
};

export const listRequiredAssets = (project: RemotionProject): string[] => {
  const assets = new Set<string>();
  Object.values(project.mascot).forEach((asset) => asset && assets.add(asset));
  project.scenes.forEach((scene) => {
    if (scene.approved && scene.image) assets.add(scene.image);
    assets.add(scene.narrationAudio);
    const approvedVideo = selectApprovedVideoSource(scene);
    if (approvedVideo) assets.add(approvedVideo.src);
    if (scene.comparisonImage) assets.add(scene.comparisonImage);
    Object.values(scene.parallax ?? {}).forEach((asset) => asset && assets.add(asset));
    scene.sfx?.forEach((sfx) => assets.add(sfx.src));
  });
  if (project.audio?.bgm) assets.add(project.audio.bgm);
  return [...assets];
};

export const validateProjectAssets = async (
  project: RemotionProject,
  exists: (asset: string) => Promise<boolean>,
): Promise<void> => {
  for (const asset of listRequiredAssets(project)) {
    if (!(await exists(asset))) {
      throw new Error(`[Remotion project] Missing asset: ${asset}`);
    }
  }
};

export const loadProject = async (
  locator: ProjectLocator,
  fetchJson: (url: string) => Promise<unknown> = async (url) => {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Unable to load ${url}: HTTP ${response.status}`);
    return response.json();
  },
): Promise<RemotionProject> => {
  if (locator.project) return normalizeProject(locator.project);
  const url = staticFile(projectAssetPath(locator.projectSlug, locator.configFile));
  return normalizeProject(await fetchJson(url));
};
