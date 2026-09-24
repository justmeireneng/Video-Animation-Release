import {Freeze, interpolate, Loop, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {selectApprovedVideoSource} from '../loaders/projectLoader';
import type {Scene} from '../types/scene';
import {SceneImage} from './SceneImage';

type Props = {scene: Scene; projectSlug: string; fullBleed?: boolean};

export const SceneVisual = ({scene, projectSlug, fullBleed = false}: Props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const durationInFrames = scene.durationInFrames;
  const source = selectApprovedVideoSource(scene);
  if (!source) return <SceneImage scene={scene} projectSlug={projectSlug} />;

  const trimBefore = Math.max(0, Math.round(source.trim.start * fps));
  const trimAfter = Math.max(trimBefore + 1, Math.round(source.trim.end * fps));
  const playbackRate = Math.min(2, Math.max(0.5, source.playbackRate ?? 1));
  const visibleFrames = Math.max(1, Math.round((trimAfter - trimBefore) / playbackRate));
  const sourceEndFrame = Math.min(visibleFrames, durationInFrames);
  const holdFrames = Math.max(0, durationInFrames - visibleFrames);
  // Keep legacy/partially migrated source projections audible by default. An
  // explicit `mute` policy still wins; this fallback only applies when the
  // imported source has no audio metadata at all.
  const audio = source.sourceAudio ?? {mode: 'background', enabled: true, volume: 0.30, duck_under_narration: true, fade_in: 0.15, fade_out: 0.20};
  const narrationActive = scene.subtitle.some((phrase) => frame >= phrase.startFrame && frame < phrase.endFrame);
  const duck = audio.mode === 'background' && audio.duck_under_narration && narrationActive ? 0.45 : 1;
  const fadeInFrames = Math.max(1, Math.round(audio.fade_in * fps));
  const fadeOutFrames = Math.max(1, Math.round(audio.fade_out * fps));
  const fadeIn = interpolate(frame, [0, fadeInFrames], [0, 1], {extrapolateRight: 'clamp'});
  // Fade source audio at the end of the narration-driven scene, not when the
  // visual clip ends. This lets an ASMR bed continue while the last frame is
  // held for a longer narration.
  const fadeOut = interpolate(frame, [Math.max(0, durationInFrames - fadeOutFrames), durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const sourceVolume = audio.enabled && audio.mode !== 'mute' ? audio.volume * duck * fadeIn * fadeOut : 0;
  const holdScale = holdFrames > Math.round(1.5 * fps)
    ? interpolate(Math.max(0, frame - visibleFrames), [0, holdFrames], [1, 1.03], {extrapolateRight: 'clamp'})
    : 1;
  const style = {
    width: '100%',
    height: '100%',
    objectFit: source.crop.mode,
    objectPosition: `${source.crop.x * 100}% ${source.crop.y * 100}%`,
  } as const;
  const video = () => (
    <OffthreadVideo
      src={staticFile(`${projectSlug}/${source.src}`)}
      trimBefore={trimBefore}
      trimAfter={trimAfter}
      playbackRate={playbackRate}
      muted
      volume={0}
      style={style}
    />
  );
  // Read the final source frame directly instead of freezing the playback
  // timeline. This remains reliable when the clip was slowed to 0.95x before
  // the narration-required hold begins.
  const lastFrameVideo = (
    <OffthreadVideo
      src={staticFile(`${projectSlug}/${source.src}`)}
      trimBefore={Math.max(trimBefore, trimAfter - 1)}
      trimAfter={trimAfter}
      muted
      volume={0}
      style={style}
    />
  );
  const sourceAudio = audio.enabled && audio.mode !== 'mute' ? (
    <div style={{position: 'absolute', width: 1, height: 1, opacity: 0, pointerEvents: 'none'}}>
      <OffthreadVideo
        src={staticFile(`${projectSlug}/${source.src}`)}
        trimBefore={trimBefore}
        trimAfter={trimAfter}
        playbackRate={playbackRate}
        muted={false}
        volume={sourceVolume}
        style={{width: 1, height: 1}}
      />
    </div>
  ) : null;

  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden', borderRadius: fullBleed ? 0 : 34, background: '#172131'}}>
      <SceneImage scene={scene} projectSlug={projectSlug} />
      {source.loop ? (
        <Loop durationInFrames={visibleFrames}>{video()}</Loop>
      ) : (
        <Sequence durationInFrames={Math.min(visibleFrames, durationInFrames)}>{video()}</Sequence>
      )}
      {sourceAudio ? (source.holdLastFrame || source.loop ? (
        <Loop durationInFrames={durationInFrames}>{sourceAudio}</Loop>
      ) : (
        <Sequence durationInFrames={Math.min(visibleFrames, durationInFrames)}>{sourceAudio}</Sequence>
      )) : null}
      {source.holdLastFrame && visibleFrames < durationInFrames ? (
        <Sequence from={visibleFrames} durationInFrames={durationInFrames - visibleFrames}>
          <div style={{width: '100%', height: '100%', transform: `scale(${holdScale})`}}>
            <Freeze frame={0}>{lastFrameVideo}</Freeze>
          </div>
        </Sequence>
      ) : null}
    </div>
  );
};
