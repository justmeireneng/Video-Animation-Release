import type {ReactNode} from 'react';
import {AbsoluteFill, getRemotionEnvironment} from 'remotion';

export const SafeZone = ({children}: {children?: ReactNode}) => {
  const {isStudio} = getRemotionEnvironment();
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {children}
      {isStudio ? (
        <div
          style={{
            position: 'absolute',
            inset: '72px 54px 250px',
            border: '2px dashed rgba(255,255,255,0.22)',
            borderRadius: 30,
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};
