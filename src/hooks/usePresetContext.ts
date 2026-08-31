import { useEffect, useMemo, useState } from 'react';

import { fontFileFor, resolveFontPathsFor } from '../engine/renderContext';
import type { RenderContext, StyleParams } from '../types/fontTypes';

/**
 * Render context for an arbitrary style (used by gallery cards).
 *
 * Styles built from ovals or SVG stamps resolve synchronously. Styles using
 * font-symbol modules need outlines from a local face, so they return `null`
 * until the font is parsed. Outlines are cached per file, which keeps a gallery
 * of 100+ styles down to a handful of fetches.
 */
export function usePresetContext(params: StyleParams): RenderContext | null {
  const fontFile = fontFileFor(params);
  const [fontPaths, setFontPaths] = useState<Readonly<Record<string, string>>>({});
  const [fontAlphabet, setFontAlphabet] = useState('');
  const [ready, setReady] = useState(() => fontFile === '');

  const requestKey = `${fontFile}|${params.moduleFontChars}`;

  useEffect(() => {
    if (!fontFile) {
      setFontPaths({});
      setFontAlphabet('');
      setReady(true);
      return;
    }

    let cancelled = false;
    setReady(false);
    resolveFontPathsFor(params)
      .then((resolved) => {
        if (cancelled) {
          return;
        }
        setFontPaths(resolved.paths);
        setFontAlphabet(resolved.alphabet);
      })
      .catch(() => {
        if (!cancelled) {
          setFontPaths({});
          setFontAlphabet('');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setReady(true);
        }
      });

    return () => {
      cancelled = true;
    };
    // Only the font file and character string can invalidate the outlines.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey]);

  return useMemo(
    () => (ready ? { params, fontPaths, fontAlphabet } : null),
    [ready, params, fontPaths, fontAlphabet],
  );
}
