import {useCurrentFrame} from 'remotion';
import type {SubtitlePhrase} from '../types/scene';

const renderWords = (phrase: SubtitlePhrase) => {
  const keywords = new Set((phrase.keywords ?? []).map((word) => word.toLocaleLowerCase('vi')));
  return phrase.text.split(/(\s+)/).map((token, index) => {
    const normalized = token.replace(/[.,:;!?]/g, '').toLocaleLowerCase('vi');
    return keywords.has(normalized) ? <span key={`${token}-${index}`} style={{color: '#ffbd45'}}>{token}</span> : token;
  });
};

export const Subtitle = ({phrases, offsetY = 0}: {phrases: SubtitlePhrase[]; offsetY?: number}) => {
  const frame = useCurrentFrame();
  const current = phrases.find((phrase) => frame >= phrase.startFrame && frame < phrase.endFrame);
  if (!current) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: 70,
        right: 70,
        bottom: 250 + offsetY,
        display: 'flex',
        justifyContent: 'center',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          maxWidth: 860,
          padding: '18px 30px 22px',
          borderRadius: 24,
          background: 'rgba(11,20,34,0.88)',
          color: '#fff',
          textAlign: 'center',
          fontFamily: '"Be Vietnam Pro", sans-serif',
          fontSize: 58,
          fontWeight: 700,
          lineHeight: 1.08,
          letterSpacing: -1,
          boxShadow: '0 12px 28px rgba(0,0,0,0.28)',
          WebkitTextStroke: '1px rgba(0,0,0,0.3)',
        }}
      >
        {renderWords(current)}
      </div>
    </div>
  );
};
