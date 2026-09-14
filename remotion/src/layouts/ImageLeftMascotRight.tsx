import type {LayoutProps} from './types';

export const ImageLeftMascotRight = ({image, mascot}: LayoutProps) => (
  <>
    <div style={{position: 'absolute', left: 46, top: 170, width: 760, height: 1260, border: '10px solid rgba(255,255,255,0.92)', borderRadius: 42, boxShadow: '0 28px 60px rgba(6,18,34,0.35)', overflow: 'hidden'}}>{image}</div>
    <div style={{position: 'absolute', right: 18, top: 1030}}>{mascot}</div>
  </>
);
