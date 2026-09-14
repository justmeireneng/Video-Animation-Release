import {getRemotionEnvironment} from 'remotion';
import {getSceneSourceType, selectApprovedVideoSource} from '../loaders/projectLoader';
import type {Scene} from '../types/scene';

export const SceneSourceBadge = ({scene}: {scene: Scene}) => {
  if (!getRemotionEnvironment().isStudio) return null;
  const source = selectApprovedVideoSource(scene);
  const label = getSceneSourceType(scene);
  return (
    <div style={{position: 'absolute', top: 74, left: 54, padding: '12px 18px', borderRadius: 14, color: '#fff', background: 'rgba(8,18,32,0.82)', fontSize: 22, fontWeight: 700, letterSpacing: 0.4}}>
      {scene.id.toUpperCase()} · SOURCE: {label}{source ? ` · V${source.version}` : ''}
    </div>
  );
};
