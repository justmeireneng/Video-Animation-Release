export const animationPresets = [
  'slow_push_in',
  'slow_zoom_out',
  'pan_left_to_right',
  'pan_right_to_left',
  'gentle_vertical_pan',
  'parallax',
  'focus_shift',
  'comparison_reveal',
  'sequential_blocks',
  'highlight_object',
  'card_entrance',
  'soft_slide',
  'crossfade',
  'wipe_reveal',
] as const;

export type AnimationPreset = (typeof animationPresets)[number];

export const layouts = [
  'full_bleed',
  'image_left_mascot_right',
  'image_center_mascot_corner',
  'full_image_mascot_overlay',
  'comparison_split',
] as const;

export type SceneLayout = (typeof layouts)[number];

export const mascotPoses = [
  'idle',
  'talking',
  'explain',
  'point_left',
  'point_right',
  'surprised',
  'thinking',
  'happy',
] as const;

export type MascotPose = (typeof mascotPoses)[number];

export type SubtitlePhrase = {
  startFrame: number;
  endFrame: number;
  text: string;
  keywords?: string[];
};

export type FocalPoint = {x: number; y: number};

export type SceneSfx = {
  src: string;
  startFrame?: number;
  volume?: number;
};

export type SceneVideoSource = {
  src: string;
  provider: string;
  sourceFilename?: string;
  version: number;
  review: 'pending_review' | 'approved' | 'rejected' | 'available';
  duration: number;
  trim: {start: number; end: number};
  crop: {mode: 'cover' | 'contain'; x: number; y: number};
  playbackRate?: number;
  holdLastFrame?: boolean;
  loop?: boolean;
  sourceAudio?: {
    mode: 'mute' | 'background' | 'full';
    enabled: boolean;
    volume: number;
    duck_under_narration: boolean;
    fade_in: number;
    fade_out: number;
    audio_duration?: number;
  };
};

export type Scene = {
  id: string;
  index: number;
  approved: boolean;
  durationInFrames: number;
  narrationOffsetFrames?: number;
  image?: string;
  comparisonImage?: string;
  narration: string;
  narrationAudio: string;
  subtitle: SubtitlePhrase[];
  layout: SceneLayout;
  mascotPose: MascotPose;
  animation: {
    type: AnimationPreset;
    scaleFrom?: number;
    scaleTo?: number;
  };
  focalPoint: FocalPoint;
  transition: 'soft_slide' | 'crossfade' | 'wipe_reveal' | 'zoom_dissolve' | 'paper' | 'none';
  subtitleOffsetY?: number;
  parallax?: {
    background?: string;
    midground?: string;
    foreground?: string;
  };
  sfx?: SceneSfx[];
  videoSources?: SceneVideoSource[];
  currentVideoVersion?: number | null;
};

export type ProjectAudio = {
  bgm?: string;
  bgmVolume?: number;
};

export type RemotionProject = {
  name: string;
  fps: number;
  width: number;
  height: number;
  style: 'cartoon_explainer';
  mascot: Partial<Record<MascotPose, string>> & {idle: string};
  scenes: Scene[];
  audio?: ProjectAudio;
};

export type ProjectLocator = {
  projectSlug: string;
  configFile: string;
  project?: RemotionProject;
};
