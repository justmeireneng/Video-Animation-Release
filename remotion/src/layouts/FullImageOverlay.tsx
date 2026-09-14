import type {LayoutProps} from './types';

export const FullImageOverlay = ({image, mascot}: LayoutProps) => (
  <>
    <div style={{position: 'absolute', inset: '54px 34px 205px', borderRadius: 46, overflow: 'hidden', boxShadow: '0 28px 70px rgba(6,18,34,0.38)'}}>{image}</div>
    <div style={{position: 'absolute', right: 34, top: 1040}}>{mascot}</div>
  </>
);
