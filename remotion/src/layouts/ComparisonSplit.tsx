import type {LayoutProps} from './types';

export const ComparisonSplit = ({image, mascot}: LayoutProps) => (
  <>
    <div style={{position: 'absolute', left: 42, top: 190, width: 996, height: 1180, border: '10px solid #fff', borderRadius: 42, overflow: 'hidden', boxShadow: '0 28px 60px rgba(6,18,34,0.35)'}}>
      {image}
      <div style={{position: 'absolute', top: 0, bottom: 0, left: '50%', width: 6, background: '#fff', boxShadow: '0 0 16px rgba(0,0,0,0.35)'}} />
      <div style={{position: 'absolute', left: 22, top: 22, padding: '10px 18px', borderRadius: 99, background: '#172131', color: '#fff', font: '800 26px Arial'}}>A</div>
      <div style={{position: 'absolute', right: 22, top: 22, padding: '10px 18px', borderRadius: 99, background: '#ffbd45', color: '#172131', font: '800 26px Arial'}}>B</div>
    </div>
    <div style={{position: 'absolute', right: 36, top: 1060}}>{mascot}</div>
  </>
);
