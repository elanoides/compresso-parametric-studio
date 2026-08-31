/**
 * Bridge between style parameters and the outline data the renderer needs.
 *
 * Font-symbol modules require glyph outlines from a local face, which arrive
 * asynchronously. Everything else renders synchronously, so this module keeps
 * the async part isolated and cached.
 */

import { resolveFontFile } from '../data/moduleFontCatalog';
import { MODULE_FONT, type StyleParams } from '../types/fontTypes';
import { EMPTY_FONT_PATH_SET, loadExtraCharPaths, loadFontPathSet } from './fontPaths';

export interface ResolvedFontPaths {
  filename: string;
  paths: Readonly<Record<string, string>>;
  alphabet: string;
}

const EMPTY: ResolvedFontPaths = { filename: '', paths: {}, alphabet: '' };

const combinedCache = new Map<string, ResolvedFontPaths>();

/** Which font file a style needs, or an empty string when it needs none. */
export function fontFileFor(params: StyleParams): string {
  if (params.moduleType !== MODULE_FONT) {
    return '';
  }
  return resolveFontFile(params.moduleFontSubfamily, params.moduleFontWeight);
}

/**
 * Resolve the outline set for a style, including any characters typed into
 * «Строка символов» that fall outside the default readable pool.
 */
export async function resolveFontPathsFor(
  params: StyleParams,
): Promise<ResolvedFontPaths> {
  const filename = fontFileFor(params);
  if (!filename) {
    return EMPTY;
  }

  const extraChars = [
    ...new Set(
      [...params.moduleFontChars.trim()]
        .filter((ch) => !/\s/.test(ch))
        .map((ch) => (ch === 'ё' ? 'Ё' : ch.toUpperCase())),
    ),
  ].join('');

  const cacheKey = `${filename}|${extraChars}`;
  const cached = combinedCache.get(cacheKey);
  if (cached) {
    return cached;
  }

  let base = EMPTY_FONT_PATH_SET;
  try {
    base = await loadFontPathSet(filename);
  } catch {
    return EMPTY;
  }

  let paths = base.paths;
  if (extraChars) {
    const missing = [...extraChars].filter((ch) => !base.paths[ch]).join('');
    if (missing) {
      const extra = await loadExtraCharPaths(filename, missing);
      paths = { ...base.paths, ...extra };
    }
  }

  const resolved: ResolvedFontPaths = {
    filename,
    paths,
    alphabet: base.alphabet,
  };
  combinedCache.set(cacheKey, resolved);
  return resolved;
}
