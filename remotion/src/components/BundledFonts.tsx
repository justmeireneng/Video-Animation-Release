import {continueRender, delayRender} from 'remotion';
import {useEffect, useState} from 'react';
import regularFont from '../../../assets/fonts/BeVietnamPro-Regular.ttf';
import semiBoldFont from '../../../assets/fonts/BeVietnamPro-SemiBold.ttf';
import boldFont from '../../../assets/fonts/BeVietnamPro-Bold.ttf';

const fontFiles = [
  {src: regularFont, weight: '400'},
  {src: semiBoldFont, weight: '600'},
  {src: boldFont, weight: '700'},
] as const;

let loadPromise: Promise<void> | undefined;

const loadFonts = (): Promise<void> => {
  if (loadPromise) return loadPromise;
  loadPromise = Promise.all(fontFiles.map(async ({src, weight}) => {
    const face = new FontFace('Be Vietnam Pro', `url(${src})`, {weight});
    const loaded = await face.load();
    document.fonts.add(loaded);
  })).then(() => undefined);
  return loadPromise;
};

export const BundledFonts = () => {
  const [handle] = useState(() => delayRender('Loading bundled Be Vietnam Pro fonts'));
  useEffect(() => {
    loadFonts().then(() => continueRender(handle)).catch((error) => {
      continueRender(handle);
      throw error;
    });
  }, [handle]);
  return null;
};
