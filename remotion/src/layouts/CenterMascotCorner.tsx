import type {LayoutProps} from './types';

export const CenterMascotCorner = ({image, mascot}: LayoutProps) => (
  <>
    <div style={{position: 'absolute', left: 50, top: 145, width: 980, height: 1370, border: '10px solid rgba(255,255,255,0.94)', borderRadius: 44, boxShadow: '0 28px 60px rgba(6,18,34,0.34)', overflow: 'hidden'}}>{image}</div>
    <div style={{position: 'absolute', right: 30, top: 1140}}>{mascot}</div>
  </>
);
