/**
 * Font-symbol modules: load a local SB Sans face, pull each glyph's outline and
 * normalize it into a unit box centred on the origin (Y-up, same orientation as
 * font space). Scaling is strictly uniform, so symbols never stretch or mirror.
 */

import type * as opentype from 'opentype.js';

import { READABLE_CHAR_POOL } from '../data/charPool';
import {
  type PathSegment,
  multiply,
  scaling,
  segmentsBBox,
  segmentsToPathData,
  transformSegments,
  translation,
} from './svgPath';

const FONT_BASE = `${import.meta.env.BASE_URL}fonts/`;

/** Outlines for one font file, keyed by character. */
export interface FontPathSet {
  filename: string;
  paths: Readonly<Record<string, string>>;
  alphabet: string;
}

const EMPTY_SET: FontPathSet = { filename: '', paths: {}, alphabet: '' };

const fontCache = new Map<string, Promise<opentype.Font>>();
const pathSetCache = new Map<string, FontPathSet>();

function loadFont(filename: string): Promise<opentype.Font> {
  const cached = fontCache.get(filename);
  if (cached) {
    return cached;
  }
  // The parser is only needed once a font-symbol module is actually in use.
  const promise = Promise.all([
    import('opentype.js'),
    fetch(`${FONT_BASE}${encodeURIComponent(filename)}`).then((response) => {
      if (!response.ok) {
        throw new Error(`Не удалось загрузить шрифт ${filename} (${response.status})`);
      }
      return response.arrayBuffer();
    }),
  ])
    .then(([opentypeModule, buffer]) => opentypeModule.parse(buffer))
    .catch((error: unknown) => {
      // Allow a later retry instead of caching the failure forever.
      fontCache.delete(filename);
      throw error;
    });
  fontCache.set(filename, promise);
  return promise;
}

function commandsToSegments(commands: readonly opentype.PathCommand[]): PathSegment[] {
  const out: PathSegment[] = [];
  for (const cmd of commands) {
    switch (cmd.type) {
      case 'M':
        out.push({ type: 'M', x: cmd.x, y: cmd.y });
        break;
      case 'L':
        out.push({ type: 'L', x: cmd.x, y: cmd.y });
        break;
      case 'C':
        out.push({
          type: 'C',
          x1: cmd.x1,
          y1: cmd.y1,
          x2: cmd.x2,
          y2: cmd.y2,
          x: cmd.x,
          y: cmd.y,
        });
        break;
      case 'Q':
        out.push({ type: 'Q', x1: cmd.x1, y1: cmd.y1, x: cmd.x, y: cmd.y });
        break;
      case 'Z':
        out.push({ type: 'Z' });
        break;
    }
  }
  return out;
}

/**
 * Normalize a glyph outline so its longest side is exactly 1 unit and its
 * bounding box is centred on the origin. One uniform factor on both axes keeps
 * the letterform's proportions intact.
 */
function normalizeToUnitBox(segments: readonly PathSegment[]): PathSegment[] | null {
  if (segments.length === 0) {
    return null;
  }
  const bbox = segmentsBBox(segments);
  const width = bbox.x1 - bbox.x0;
  const height = bbox.y1 - bbox.y0;
  const longest = Math.max(width, height);
  if (!Number.isFinite(longest) || longest <= 1e-9) {
    return null;
  }
  const uniform = 1 / longest;
  const centreX = (bbox.x0 + bbox.x1) / 2;
  const centreY = (bbox.y0 + bbox.y1) / 2;
  return transformSegments(
    segments,
    multiply(scaling(uniform, uniform), translation(-centreX, -centreY)),
  );
}

function glyphPathData(font: opentype.Font, ch: string): string {
  const glyph = font.charToGlyph(ch);
  if (!glyph || glyph.index === 0) {
    return '';
  }
  const normalized = normalizeToUnitBox(commandsToSegments(glyph.path.commands));
  return normalized ? segmentsToPathData(normalized, 5) : '';
}

/**
 * Build (and memoize) all outlines for one font file across the readable pool.
 * Resolves to an empty set when the file cannot be loaded.
 */
export async function loadFontPathSet(filename: string): Promise<FontPathSet> {
  if (!filename) {
    return EMPTY_SET;
  }
  const cached = pathSetCache.get(filename);
  if (cached) {
    return cached;
  }

  const font = await loadFont(filename);
  const paths: Record<string, string> = {};
  let alphabet = '';

  for (const ch of READABLE_CHAR_POOL) {
    const data = glyphPathData(font, ch);
    if (data) {
      paths[ch] = data;
      alphabet += ch;
    }
  }

  const set: FontPathSet = { filename, paths, alphabet };
  pathSetCache.set(filename, set);
  return set;
}

/**
 * Outlines for an explicit character string (e.g. the «Строка символов» field),
 * merged into the base pool so custom symbols outside the pool still render.
 */
export async function loadExtraCharPaths(
  filename: string,
  chars: string,
): Promise<Readonly<Record<string, string>>> {
  if (!filename || !chars) {
    return {};
  }
  const font = await loadFont(filename);
  const out: Record<string, string> = {};
  for (const ch of chars) {
    if (out[ch] !== undefined) {
      continue;
    }
    const data = glyphPathData(font, ch);
    if (data) {
      out[ch] = data;
    }
  }
  return out;
}

export const EMPTY_FONT_PATH_SET = EMPTY_SET;
