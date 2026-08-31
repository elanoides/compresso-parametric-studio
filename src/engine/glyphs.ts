/**
 * All-Caps glyph access layer.
 *
 * The grid is 28 rows tall:
 *   rows  0..3   accents (Ё, Й diacritics)
 *   rows  4..23  cap-height body (20 rows)
 *   row     23   baseline — every glyph in a line sits on it
 *   rows 24..27  descenders (Ц, Щ tails, Д legs)
 */

import {
  BASELINE,
  GLYPHS,
  GLYPH_CHARS,
  GLYPH_WIDTHS,
  ROWS_TOTAL,
  SPACE_WIDTH_COLS,
} from '../data/glyphsData';
import type { GlyphMatrix, GridCoord } from '../types/fontTypes';

export {
  ACCENT_BOTTOM,
  ACCENT_TOP,
  BASELINE,
  BODY_BOTTOM,
  BODY_TOP,
  CAP_HEIGHT,
  DESC_BOTTOM,
  DESC_TOP,
  GLYPHS,
  GLYPH_CHARS,
  GLYPH_WIDTHS,
  ROWS_TOTAL,
  SPACE_WIDTH_COLS,
} from '../data/glyphsData';

const EMPTY: GlyphMatrix = [];

/** Space or an unsupported character — laid out as an advance with no ink. */
export function isBlank(ch: string): boolean {
  return ch === ' ' || ch === '';
}

/**
 * Map an input character onto a glyph key: whitespace folds to a space,
 * line breaks are dropped, `ё` folds to `Ё`, everything else upper-cases.
 * Returns `null` for characters that should be skipped entirely.
 */
export function resolveGlyphKey(ch: string): string | null {
  if (ch === ' ' || ch === '\t') {
    return ' ';
  }
  if (ch === '\n' || ch === '\r' || ch === '\v' || ch === '\f') {
    return null;
  }
  const folded = ch === 'ё' || ch === 'Ё' ? 'Ё' : ch.toUpperCase();
  return folded in GLYPHS ? folded : '';
}

/** All-Caps normalization: one entry per rendered character. */
export function normalizeText(text: string): string[] {
  const out: string[] = [];
  for (const ch of text) {
    const key = resolveGlyphKey(ch);
    if (key !== null) {
      out.push(key);
    }
  }
  return out;
}

/** Advance width of a glyph in grid columns. */
export function glyphWidth(ch: string): number {
  if (isBlank(ch)) {
    return SPACE_WIDTH_COLS;
  }
  const known = GLYPH_WIDTHS[ch];
  if (known !== undefined) {
    return Math.max(1, known);
  }
  const coords = GLYPHS[ch];
  if (!coords || coords.length === 0) {
    return SPACE_WIDTH_COLS;
  }
  let maxCol = 0;
  for (const [col] of coords) {
    if (col > maxCol) {
      maxCol = col;
    }
  }
  return maxCol + 1;
}

export function scaledWidth(ch: string, colScale: number): number {
  return glyphWidth(ch) * Math.max(1, colScale);
}

/**
 * Multiply module density: every cell becomes a `colScale × rowScale` block.
 * Rows are squashed back into the 28-row grid so the baseline stays put.
 */
function scaleGlyphDensity(
  coords: GlyphMatrix,
  colScale: number,
  rowScale: number,
): GlyphMatrix {
  const expanded = new Map<number, GridCoord>();
  for (const [col, row] of coords) {
    for (let dr = 0; dr < rowScale; dr += 1) {
      for (let dc = 0; dc < colScale; dc += 1) {
        const c = col * colScale + dc;
        const r = row * rowScale + dr;
        expanded.set(c * 4096 + r, [c, r]);
      }
    }
  }

  let list = [...expanded.values()];

  if (rowScale > 1) {
    const maxRow = ROWS_TOTAL * rowScale - 1;
    const squashed = new Map<number, GridCoord>();
    for (const [col, row] of list) {
      const r = Math.round((row * (ROWS_TOTAL - 1)) / maxRow);
      squashed.set(col * 4096 + r, [col, r]);
    }
    list = [...squashed.values()];
  }

  list.sort((a, b) => a[1] - b[1] || a[0] - b[0]);
  return list;
}

const densityCache = new Map<string, GlyphMatrix>();

/** Module coordinates for one character at the given matrix multipliers. */
export function getGlyph(ch: string, colScale: number, rowScale: number): GlyphMatrix {
  const base = GLYPHS[ch];
  if (!base || base.length === 0) {
    return EMPTY;
  }
  if (colScale <= 1 && rowScale <= 1) {
    return base;
  }
  const key = `${ch}|${colScale}|${rowScale}`;
  const cached = densityCache.get(key);
  if (cached) {
    return cached;
  }
  const scaled = scaleGlyphDensity(base, colScale, rowScale);
  densityCache.set(key, scaled);
  return scaled;
}

/** Characters offered in the glyph inspector, in alphabet order. */
export const INSPECTOR_CHARS: readonly string[] = GLYPH_CHARS;

/** Row index of the baseline — exported for guide drawing. */
export const BASELINE_ROW = BASELINE;
