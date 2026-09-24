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
  const audio = source.sourceAudio ?? {mode: 'mute', enabled: false, volume: 0, duck_under_narration: true, fade_in: 0, fade_out: 0};
  const narrationActive = scene.subtitle.some((phrase) => frame >= phrase.startFrame && frame < phrase.endFrame);
  const duck = audio.mode === 'background' && audio.duck_under_narration && narrationActive ? 0.45 : 1;
  const fadeInFrames = Math.max(1, Math.round(audio.fade_in * fps));
  const fadeOutFrames = Math.max(1, Math.round(audio.fade_out * fps));
  const fadeIn = interpolate(frame, [0, fadeInFrames], [0, 1], {extrapolateRight: 'clamp'});
  const fadeOut = interpolate(frame, [Math.max(0, sourceEndFrame - fadeOutFrames), sourceEndFrame], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
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
  const video = (muted = sourceVolume === 0) => (
    <OffthreadVideo
      src={staticFile(`${projectSlug}/${source.src}`)}
      trimBefore={trimBefore}
      trimAfter={trimAfter}
      playbackRate={playbackRate}
      muted={muted}
      volume={muted ? 0 : sourceVolume}
      style={style}
    />
  );

  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden', borderRadius: fullBleed ? 0 : 34, background: '#172131'}}>
      <SceneImage scene={scene} projectSlug={projectSlug} />
      {source.loop ? (
        <Loop durationInFrames={visibleFrames}>{video()}</Loop>
      ) : (
        <Sequence durationInFrames={Math.min(visibleFrames, durationInFrames)}>{video()}</Sequence>
      )}
      {source.holdLastFrame && visibleFrames < durationInFrames ? (
        <Sequence from={visibleFrames} durationInFrames={durationInFrames - visibleFrames}>
          <div style={{width: '100%', height: '100%', transform: `scale(${holdScale})`}}>
            <Freeze frame={visibleFrames - 1}>{video(true)}</Freeze>
          </div>
        </Sequence>
      ) : null}
    </div>
  );
};
