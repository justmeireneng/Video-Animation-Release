import {describe, expect, it} from 'vitest';
import {
  DEFAULT_ANIMATION,
  getProjectDuration,
  loadProject,
  normalizeProject,
  getSceneSourceType,
  selectApprovedVideoSource,
  validateProjectAssets,
} from './projectLoader';

const scene = (overrides: Record<string, unknown> = {}) => ({
  id: 'scene_01',
  index: 1,
  approved: true,
  durationInFrames: 90,
  image: 'scenes/01.png',
  narration: 'Test narration',
  narrationAudio: 'audio/01.wav',
  subtitle: [{startFrame: 0, endFrame: 80, text: 'A short phrase'}],
  layout: 'image_left_mascot_right',
  mascotPose: 'talking',
  animation: {type: 'slow_push_in'},
  focalPoint: {x: 0.6, y: 0.4},
  transition: 'crossfade',
  ...overrides,
});

const fixture = (scenes = [scene()]) => ({
  name: 'Fixture',
  fps: 30,
  width: 1080,
  height: 1920,
  style: 'cartoon_explainer',
  mascot: {idle: 'mascot/idle.png'},
  scenes,
});

describe('projectLoader', () => {
  it('reads project JSON through the injected loader', async () => {
    const project = await loadProject(
      {projectSlug: 'Fixture', configFile: 'remotion.json'},
      async () => fixture(),
    );
    expect(project.name).toBe('Fixture');
    expect(project.scenes).toHaveLength(1);
  });

  it('calculates total duration', () => {
    const project = normalizeProject(fixture([scene({durationInFrames: 60}), scene({id: 'scene_02', index: 2, durationInFrames: 75})]));
    expect(getProjectDuration(project)).toBe(135);
  });

  it('orders scenes by index', () => {
    const project = normalizeProject(fixture([scene({id: 'second', index: 2}), scene({id: 'first', index: 1})]));
    expect(project.scenes.map((item) => item.id)).toEqual(['first', 'second']);
  });

  it('reports a missing asset clearly', async () => {
    const project = normalizeProject(fixture());
    await expect(validateProjectAssets(project, async (asset) => asset !== 'scenes/01.png')).rejects.toThrow('Missing asset: scenes/01.png');
  });

  it('falls back for an invalid animation preset', () => {
    const project = normalizeProject(fixture([scene({animation: {type: 'random_spin'}})]));
    expect(project.scenes[0].animation.type).toBe(DEFAULT_ANIMATION);
  });

  it('clamps subtitle timing to scene duration', () => {
    const project = normalizeProject(fixture([scene({durationInFrames: 45, subtitle: [{startFrame: -3, endFrame: 99, text: 'Safe timing'}]})]));
    expect(project.scenes[0].subtitle[0]).toMatchObject({startFrame: 0, endFrame: 45});
  });

  it('falls back missing mascot poses to idle', () => {
    const project = normalizeProject(fixture());
    expect(project.mascot.point_left).toBe('mascot/idle.png');
    expect(project.mascot.happy).toBe('mascot/idle.png');
  });

  it('accepts a full-bleed video-only project without mascot assets', () => {
    const input = fixture([scene({layout: 'full_bleed', approved: false, image: undefined})]);
    delete (input as {mascot?: unknown}).mascot;
    const project = normalizeProject(input);
    expect(project.scenes[0].layout).toBe('full_bleed');
    expect(project.mascot.idle).toBe('');
  });

  it('uses only approved video and prioritizes Flow over other generated clips', () => {
    const project = normalizeProject(fixture([scene({videoSources: [
      {src: 'pending.mp4', provider: 'google_flow_manual', version: 3, review: 'pending_review', duration: 6, trim: {start: 0, end: 6}, crop: {mode: 'cover', x: 0.5, y: 0.5}},
      {src: 'generated.mp4', provider: 'generated_video', version: 2, review: 'approved', duration: 6, trim: {start: 0, end: 6}, crop: {mode: 'cover', x: 0.5, y: 0.5}},
      {src: 'flow.mp4', provider: 'google_flow_manual', version: 1, review: 'approved', duration: 6, trim: {start: 0, end: 6}, crop: {mode: 'cover', x: 0.5, y: 0.5}},
    ]})]));
    expect(selectApprovedVideoSource(project.scenes[0])?.src).toBe('flow.mp4');
    expect(getSceneSourceType(project.scenes[0])).toBe('FLOW_VIDEO');
  });

  it('falls back to approved still image when video is not approved', () => {
    const project = normalizeProject(fixture([scene({videoSources: [
      {src: 'pending.mp4', provider: 'google_flow_manual', version: 1, review: 'pending_review', duration: 6, trim: {start: 0, end: 6}, crop: {mode: 'cover', x: 0.5, y: 0.5}},
    ]})]));
    expect(selectApprovedVideoSource(project.scenes[0])).toBeUndefined();
    expect(getSceneSourceType(project.scenes[0])).toBe('STATIC_IMAGE');
  });
});
