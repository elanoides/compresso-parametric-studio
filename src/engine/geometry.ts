/**
 * Grid geometry and SVG emission.
 *
 * Every module sits at a `(column, row)` cell centre, then gets displaced by
 * slant, glitch jitter and scanline shift. The canvas is sized from the worst
 * case of those displacements plus the effective extents of a rotated module,
 * so nothing is ever clipped — including 45° modules and steep slant.
 */

import { RANDOM_EXCLUDED_CHARS, READABLE_CHAR_POOL } from '../data/charPool';
import {
  FILL_ORDER_ROWS,
  MODULE_CUSTOM_SVG,
  MODULE_FONT,
  MODULE_OVAL,
  type CanvasBox,
  type GlyphMatrix,
  type GridCoord,
  type PlacedModule,
  type RenderContext,
  type StyleParams,
  type TextLayout,
} from '../types/fontTypes';
import {
  BASELINE,
  BODY_BOTTOM,
  BODY_TOP,
  ROWS_TOTAL,
  SPACE_WIDTH_COLS,
  getGlyph,
  isBlank,
  normalizeText,
  scaledWidth,
} from './glyphs';
import { intPart, stableIndex, stableUnit } from './hash';
import { deserializeStamp, stampUniformScale } from './moduleStamp';
import {
  type PathSegment,
  ellipseSegments,
  multiply,
  parsePathData,
  rotationAround,
  scaling,
  segmentsToPathData,
  transformSegments,
  translation,
} from './svgPath';

/** Fixed canvas margin around the glyph ink, in SVG units. */
export const PADDING = 24;

const EPSILON = 1e-9;

function f2(value: number): string {
  return value.toFixed(2);
}

function f1(value: number): string {
  return value.toFixed(1);
}

/* ------------------------------------------------------------------ *
 * Module extents and deformation
 * ------------------------------------------------------------------ */

export function strokeMargin(p: StyleParams): number {
  return p.strokeWidth / 2;
}

export function slantTan(p: StyleParams): number {
  return Math.tan((p.slantAngle * Math.PI) / 180);
}

/** Axis-aligned half-extents of an ellipse rotated by `angleDeg`. */
export function ellipseHalfExtents(
  rx: number,
  ry: number,
  angleDeg: number,
): [number, number] {
  if (Math.abs(angleDeg) < EPSILON) {
    return [rx, ry];
  }
  const rad = (angleDeg * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  return [
    Math.sqrt((rx * cos) ** 2 + (ry * sin) ** 2),
    Math.sqrt((rx * sin) ** 2 + (ry * cos) ** 2),
  ];
}

/** Half-extents of one module including its stroke. */
export function moduleInkExtents(p: StyleParams): [number, number] {
  const margin = strokeMargin(p);
  const [hw, hh] = ellipseHalfExtents(p.rx, p.ry, p.moduleAngle);
  return [hw + margin, hh + margin];
}

/** Extra horizontal room needed so slant and jitter never clip. */
export function deformPadX(p: StyleParams): number {
  const maxAbove = BASELINE * p.stepY + p.ry;
  const maxBelow = (ROWS_TOTAL - 1 - BASELINE) * p.stepY + p.ry;
  const slantExtra = Math.abs(slantTan(p)) * Math.max(maxAbove, maxBelow);
  return slantExtra + Math.abs(p.jitterX) + Math.abs(p.rowJitter);
}

/**
 * Horizontal displacement of one module.
 *
 * Slant is measured from the baseline: `x += (yBaseline - y) * tan(θ)`.
 * Glitch jitter is per module, scanline shift is per row.
 */
export function deformOffsetX(
  col: number,
  row: number,
  cy: number,
  yBaseline: number,
  p: StyleParams,
  salt: string,
): number {
  let dx = (yBaseline - cy) * slantTan(p);
  if (p.jitterX !== 0) {
    const colQuantized = Math.round(col * 1e4) / 1e4;
    dx += p.jitterX * stableUnit(p.seed, 'jx', salt, colQuantized, intPart(row));
  }
  if (p.rowJitter !== 0) {
    dx += p.rowJitter * stableUnit(p.seed, 'row', intPart(row));
  }
  return dx;
}

/** Grid cell to deformed SVG centre. */
export function transformedCenter(
  col: number,
  row: number,
  p: StyleParams,
  originX: number,
  originY: number,
  minRow: number,
  salt: string,
): [number, number] {
  const cx = originX + col * p.stepX;
  const cy = originY + (row - minRow) * p.stepY;
  const yBaseline = originY + (BASELINE - minRow) * p.stepY;
  return [cx + deformOffsetX(col, row, cy, yBaseline, p, salt), cy];
}

/**
 * Module centre in font units (Y-up from the baseline) for outline export.
 * Slant is applied against y = 0; jitter reuses the same noise as the preview.
 */
export function moduleCenterFontUnits(
  col: number,
  row: number,
  p: StyleParams,
  scale: number,
  salt: string,
): [number, number] {
  const cx = col * p.stepX * scale;
  const cy = (BASELINE - row) * p.stepY * scale;
  let dx = cy * slantTan(p);
  if (p.jitterX !== 0) {
    const colQuantized = Math.round(col * 1e4) / 1e4;
    dx += p.jitterX * stableUnit(p.seed, 'jx', salt, colQuantized, intPart(row)) * scale;
  }
  if (p.rowJitter !== 0) {
    dx += p.rowJitter * stableUnit(p.seed, 'row', intPart(row)) * scale;
  }
  return [cx + dx, cy];
}

/* ------------------------------------------------------------------ *
 * Font-symbol assignment
 * ------------------------------------------------------------------ */

export function symbolsPerModule(p: StyleParams): number {
  return Math.max(1, Math.round(p.moduleFontSymbolsPerModule));
}

/** Uniform scale that fits `count` stacked symbols into the module height. */
export function fontUniformScale(p: StyleParams, count: number): number {
  return Math.max(p.ry - strokeMargin(p), 0.5) / Math.max(1, count);
}

/** Vertical offset of a stacked symbol from the module centre (SVG Y-down). */
export function symbolYOffset(index: number, count: number, ry: number): number {
  if (count <= 1) {
    return 0;
  }
  const strip = (2 * ry) / count;
  return (index - (count - 1) / 2) * strip;
}

function buildCharPool(ctx: RenderContext): string {
  const raw = ctx.params.moduleFontChars.trim();
  if (raw) {
    let out = '';
    for (const ch of raw) {
      if (!/\s/.test(ch)) {
        out += ch === 'ё' ? 'Ё' : ch.toUpperCase();
      }
    }
    if (out) {
      return out;
    }
  }
  return ctx.fontAlphabet || READABLE_CHAR_POOL;
}

/** Drop circle-like glyphs and anything the font cannot draw. */
function drawableCharPool(pool: string, ctx: RenderContext): string {
  let out = '';
  for (const ch of pool) {
    if (RANDOM_EXCLUDED_CHARS.has(ch)) {
      continue;
    }
    if (!ctx.fontPaths[ch]) {
      continue;
    }
    out += ch;
  }
  if (out) {
    return out;
  }
  for (const ch of pool) {
    if (ctx.fontPaths[ch]) {
      return ch;
    }
  }
  return '';
}

function cellKey(col: number, row: number): number {
  return Math.trunc(col) * 4096 + row;
}

/**
 * Assign characters to the cells of one glyph, either sequentially in the
 * chosen fill order or deterministically at random from the seed.
 */
export function fontCharMap(
  coords: GlyphMatrix,
  ctx: RenderContext,
  salt: string,
): Map<number, string[]> {
  const result = new Map<number, string[]>();
  const pool = drawableCharPool(buildCharPool(ctx), ctx);
  if (!pool) {
    return result;
  }

  const p = ctx.params;
  const ordered = [...coords].sort((a, b) =>
    p.moduleFontFillOrder === FILL_ORDER_ROWS
      ? a[1] - b[1] || a[0] - b[0]
      : a[0] - b[0] || a[1] - b[1],
  );

  const perModule = symbolsPerModule(p);
  let sequence = 0;

  for (const [col, row] of ordered) {
    const chars: string[] = [];
    for (let slot = 0; slot < perModule; slot += 1) {
      if (p.moduleFontRandomize) {
        chars.push(pool[stableIndex(p.seed, `${salt}:${col}:${row}:${slot}`, pool.length)]);
      } else {
        chars.push(pool[sequence % pool.length]);
        sequence += 1;
      }
    }
    result.set(cellKey(col, row), chars);
  }

  return result;
}

/* ------------------------------------------------------------------ *
 * Module SVG emission
 * ------------------------------------------------------------------ */

function rotateAttr(p: StyleParams, cx: number, cy: number): string {
  return Math.abs(p.moduleAngle) >= EPSILON
    ? ` transform="rotate(${f2(p.moduleAngle)}, ${f2(cx)}, ${f2(cy)})"`
    : '';
}

function ellipseModule(
  cx: number,
  cy: number,
  p: StyleParams,
  fillOpacity: number,
): string {
  return (
    `<ellipse cx="${f2(cx)}" cy="${f2(cy)}" rx="${f2(p.rx)}" ry="${f2(p.ry)}"` +
    rotateAttr(p, cx, cy) +
    ` fill="${p.fill}" fill-opacity="${fillOpacity.toFixed(3)}"` +
    ` stroke="${p.stroke}" stroke-width="${f2(p.strokeWidth)}"/>`
  );
}

const stampPathCache = new Map<string, string>();

function stampPathData(p: StyleParams): string | null {
  const shape = deserializeStamp(p.customSvgMarkup);
  if (!shape) {
    return null;
  }
  const uniform = stampUniformScale(shape, p.rx, p.ry);
  const key = `${p.customSvgMarkup.length}|${uniform.toFixed(6)}`;
  const cached = stampPathCache.get(key);
  if (cached !== undefined) {
    return cached;
  }
  const data = segmentsToPathData(
    transformSegments(shape.segments, scaling(uniform, uniform)),
    3,
  );
  stampPathCache.set(key, data);
  return data;
}

function customSvgModule(
  cx: number,
  cy: number,
  p: StyleParams,
  fillOpacity: number,
): string {
  const data = stampPathData(p);
  if (!data) {
    return ellipseModule(cx, cy, p, fillOpacity);
  }
  return (
    `<g${rotateAttr(p, cx, cy)}>` +
    `<g transform="translate(${f2(cx)},${f2(cy)})">` +
    `<path d="${data}" fill="${p.fill}" fill-opacity="${fillOpacity.toFixed(3)}"` +
    ` stroke="${p.stroke}" stroke-width="${f2(p.strokeWidth)}"/>` +
    '</g></g>'
  );
}

function fontSymbolModule(
  cx: number,
  cy: number,
  ctx: RenderContext,
  chars: readonly string[],
  fillOpacity: number,
): string {
  const p = ctx.params;
  const drawable = chars.filter((ch) => Boolean(ctx.fontPaths[ch]));
  if (drawable.length === 0) {
    return '';
  }
  const uniform = fontUniformScale(p, drawable.length);
  const parts: string[] = [`<g${rotateAttr(p, cx, cy)}>`];

  drawable.forEach((ch, index) => {
    const dy = symbolYOffset(index, drawable.length, p.ry);
    // scale(u, -u): outlines are Y-up, SVG is Y-down.
    parts.push(
      `<g transform="translate(${f2(cx)},${f2(cy + dy)}) ` +
        `scale(${uniform.toFixed(4)},${(-uniform).toFixed(4)})">` +
        `<path d="${ctx.fontPaths[ch]}" fill="${p.fill}"` +
        ` fill-opacity="${fillOpacity.toFixed(3)}" stroke="${p.stroke}"` +
        ` stroke-width="${(p.strokeWidth / uniform).toFixed(4)}"/></g>`,
    );
  });

  parts.push('</g>');
  return parts.join('');
}

function moduleSvgAt(
  cx: number,
  cy: number,
  ctx: RenderContext,
  fillOpacity: number,
  chars?: readonly string[],
): string {
  switch (ctx.params.moduleType) {
    case MODULE_OVAL:
      return ellipseModule(cx, cy, ctx.params, fillOpacity);
    case MODULE_CUSTOM_SVG:
      return customSvgModule(cx, cy, ctx.params, fillOpacity);
    case MODULE_FONT:
      return chars && chars.length > 0
        ? fontSymbolModule(cx, cy, ctx, chars, fillOpacity)
        : '';
    default:
      return '';
  }
}

/* ------------------------------------------------------------------ *
 * Canvas sizing and text layout
 * ------------------------------------------------------------------ */

export function canvasBox(
  p: StyleParams,
  maxCol: number,
  minRow: number,
  maxRow: number,
): CanvasBox {
  const extra = deformPadX(p);
  const [hw, hh] = moduleInkExtents(p);
  const rowSpan = Math.max(maxRow - minRow, 0);
  return {
    width: PADDING * 2 + Math.max(maxCol, 0) * p.stepX + hw * 2 + extra * 2,
    height: PADDING * 2 + rowSpan * p.stepY + hh * 2,
    originX: PADDING + hw + extra,
    originY: PADDING + hh - minRow * p.stepY,
  };
}

function advanceFor(ch: string, p: StyleParams): number {
  if (isBlank(ch)) {
    return SPACE_WIDTH_COLS * Math.max(1, p.colScale) + p.letterSpacing;
  }
  return scaledWidth(ch, p.colScale) + p.letterSpacing;
}

/** Place a string on the grid, applying kerning between adjacent glyphs. */
export function layoutText(text: string, p: StyleParams): TextLayout {
  const modules: PlacedModule[] = [];
  let maxCol = 0;
  let minRow = ROWS_TOTAL - 1;
  let maxRow = 0;
  let cursor = 0;
  let prev: string | null = null;

  for (const ch of normalizeText(text)) {
    if (prev !== null && !isBlank(ch) && !isBlank(prev)) {
      cursor += p.kerningPairs[prev + ch] ?? 0;
    }

    const coords = getGlyph(ch, p.colScale, p.rowScale);
    if (isBlank(ch) || coords.length === 0) {
      cursor += advanceFor(ch, p);
      prev = ch;
      continue;
    }

    for (const [col, row] of coords) {
      const absCol = cursor + col;
      if (absCol > maxCol) {
        maxCol = absCol;
      }
      if (row < minRow) {
        minRow = row;
      }
      if (row > maxRow) {
        maxRow = row;
      }
      modules.push({ col: absCol, row, char: ch });
    }

    cursor += advanceFor(ch, p);
    prev = ch;
  }

  if (cursor > 0) {
    maxCol = Math.max(maxCol, cursor - p.letterSpacing - 1);
  }

  if (modules.length === 0) {
    minRow = 0;
    maxRow = ROWS_TOTAL - 1;
  }

  return { modules, maxCol, minRow, maxRow };
}

/**
 * Tight canvas around the actual ink after slant, jitter and module rotation.
 * Origins are computed in a temporary (0, 0) space, then shifted so the
 * leftmost/topmost ink sits `PADDING` inside the viewBox.
 */
export function canvasBoxFromModules(
  p: StyleParams,
  modules: readonly PlacedModule[],
  minRow: number,
  maxCol: number,
  maxRow: number,
): CanvasBox {
  const [hw, hh] = moduleInkExtents(p);
  if (modules.length === 0) {
    return canvasBox(p, maxCol, minRow, maxRow);
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const m of modules) {
    const [cx, cy] = transformedCenter(m.col, m.row, p, 0, 0, minRow, m.char);
    minX = Math.min(minX, cx - hw);
    maxX = Math.max(maxX, cx + hw);
    minY = Math.min(minY, cy - hh);
    maxY = Math.max(maxY, cy + hh);
  }

  return {
    width: PADDING * 2 + (maxX - minX),
    height: PADDING * 2 + (maxY - minY),
    originX: PADDING - minX,
    originY: PADDING - minY,
  };
}

/* ------------------------------------------------------------------ *
 * Guides
 * ------------------------------------------------------------------ */

function gridLines(
  parts: string[],
  p: StyleParams,
  box: CanvasBox,
  cols: number,
  minRow: number,
  maxRow: number,
): void {
  const { originX: ox, originY: oy } = box;
  const xEnd = ox + Math.max(cols - 1, 0) * p.stepX;
  const yEnd = oy + (maxRow - minRow) * p.stepY;
  parts.push(`<g opacity="0.3" stroke="${p.gridColor}" stroke-width="0.5">`);
  for (let r = minRow; r <= maxRow; r += 1) {
    const y = oy + (r - minRow) * p.stepY;
    parts.push(`<line x1="${f1(ox)}" y1="${f1(y)}" x2="${f1(xEnd)}" y2="${f1(y)}"/>`);
  }
  for (let c = 0; c < cols; c += 1) {
    const x = ox + c * p.stepX;
    parts.push(`<line x1="${f1(x)}" y1="${f1(oy)}" x2="${f1(x)}" y2="${f1(yEnd)}"/>`);
  }
  parts.push('</g>');
}

function baselineGuide(
  parts: string[],
  p: StyleParams,
  box: CanvasBox,
  minRow: number,
  xEnd: number,
): void {
  const hw = moduleInkExtents(p)[0];
  const y = box.originY + (BASELINE - minRow) * p.stepY;
  parts.push(
    `<line x1="${f1(box.originX - hw)}" y1="${f1(y)}" x2="${f1(xEnd)}" y2="${f1(y)}" ` +
      `stroke="${p.guideColor}" stroke-width="1.2" opacity="0.85"/>`,
  );
}

function glyphMetricGuides(
  parts: string[],
  p: StyleParams,
  box: CanvasBox,
  cols: number,
  minRow: number,
  maxRow: number,
): void {
  const [hw, hh] = moduleInkExtents(p);
  const { originX: ox, originY: oy } = box;
  const yCap = oy + (BODY_TOP - minRow) * p.stepY;
  const yBase = oy + (BASELINE - minRow) * p.stepY;
  const yBodyBottom = oy + (BODY_BOTTOM - minRow) * p.stepY;
  const x0 = ox - hw;
  const x1 = ox + Math.max(cols - 1, 0) * p.stepX + hw;

  parts.push(
    `<rect x="${f1(x0)}" y="${f1(oy - hh)}" width="${f1(x1 - x0)}" ` +
      `height="${f1((BODY_TOP - minRow) * p.stepY)}" fill="${p.gridColor}" opacity="0.07"/>`,
  );
  const descHeight = Math.max(0, (maxRow - BODY_BOTTOM) * p.stepY + hh);
  parts.push(
    `<rect x="${f1(x0)}" y="${f1(yBodyBottom)}" width="${f1(x1 - x0)}" ` +
      `height="${f1(descHeight)}" fill="${p.guideColor}" opacity="0.07"/>`,
  );
  parts.push(
    `<line x1="${f1(x0)}" y1="${f1(yCap)}" x2="${f1(x1)}" y2="${f1(yCap)}" ` +
      `stroke="${p.gridColor}" stroke-width="1" stroke-dasharray="4 3"/>`,
  );
  parts.push(
    `<line x1="${f1(x0)}" y1="${f1(yBase)}" x2="${f1(x1)}" y2="${f1(yBase)}" ` +
      `stroke="${p.guideColor}" stroke-width="1.4"/>`,
  );
  parts.push(
    `<text x="${f1(x1 + 6)}" y="${f1(yCap + 3)}" fill="${p.gridColor}" font-size="11" ` +
      `font-family="monospace">Cap-Height · row ${BODY_TOP}</text>`,
  );
  parts.push(
    `<text x="${f1(x1 + 6)}" y="${f1(yBase + 3)}" fill="${p.guideColor}" font-size="11" ` +
      `font-family="monospace">Baseline · row ${BASELINE}</text>`,
  );
}

function gridGhosts(
  parts: string[],
  ctx: RenderContext,
  box: CanvasBox,
  cols: number,
  minRow: number,
  maxRow: number,
): void {
  const p = ctx.params;
  if (p.moduleType === MODULE_FONT) {
    return;
  }
  const ghost = Math.min(0.18, Math.max(0.04, p.fillOpacity * 0.15));
  parts.push('<g>');
  for (let r = minRow; r <= maxRow; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const [cx, cy] = transformedCenter(c, r, p, box.originX, box.originY, minRow, 'grid');
      parts.push(moduleSvgAt(cx, cy, ctx, ghost));
    }
  }
  parts.push('</g>');
}

/* ------------------------------------------------------------------ *
 * Renderers
 * ------------------------------------------------------------------ */

export interface TextSvgOptions {
  /** When false, the SVG is transparent so the host canvas shows through. */
  paintBackground?: boolean;
  /**
   * Emit `width="100%" height="100%"` with `preserveAspectRatio="xMidYMid meet"`
   * so the host box scales the whole inscription without cropping.
   */
  contain?: boolean;
}

function svgOpen(
  width: number,
  height: number,
  displayScale: number,
  contain = false,
): string {
  const viewBox = `0 0 ${f1(width)} ${f1(height)}`;
  const aspect = 'preserveAspectRatio="xMidYMid meet"';
  if (contain) {
    return (
      `<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" ` +
      `viewBox="${viewBox}" ${aspect}>`
    );
  }
  const w = width * displayScale;
  const h = height * displayScale;
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${f1(w)}" height="${f1(h)}" ` +
    `viewBox="${viewBox}" ${aspect}>`
  );
}

/** Render a baseline-aligned string to a standalone SVG document. */
export function renderTextSvg(
  text: string,
  ctx: RenderContext,
  displayScale = 1,
  options?: TextSvgOptions,
): string {
  const p = ctx.params;
  const { modules, maxCol, minRow, maxRow } = layoutText(text, p);
  const box = canvasBoxFromModules(p, modules, minRow, maxCol, maxRow);
  const paintBackground = options?.paintBackground !== false;
  const contain = options?.contain === true;

  const parts: string[] = [
    svgOpen(box.width, box.height, Math.max(0.05, displayScale), contain),
  ];
  if (paintBackground) {
    parts.push(`<rect width="100%" height="100%" fill="${p.background}"/>`);
  }

  const charMaps = new Map<string, Map<number, string[]>>();
  if (p.moduleType === MODULE_FONT) {
    const perChar = new Map<string, GridCoord[]>();
    for (const m of modules) {
      const bucket = perChar.get(m.char);
      const coord: GridCoord = [Math.trunc(m.col), m.row];
      if (bucket) {
        bucket.push(coord);
      } else {
        perChar.set(m.char, [coord]);
      }
    }
    for (const [ch, coords] of perChar) {
      charMaps.set(ch, fontCharMap(coords, ctx, ch));
    }
  }

  if (p.showGrid) {
    gridLines(parts, p, box, Math.ceil(maxCol) + 1, minRow, maxRow);
  }
  if (p.showGuides) {
    const hw = moduleInkExtents(p)[0];
    baselineGuide(parts, p, box, minRow, box.originX + maxCol * p.stepX + hw);
  }

  parts.push('<g>');
  for (const m of modules) {
    const [cx, cy] = transformedCenter(
      m.col,
      m.row,
      p,
      box.originX,
      box.originY,
      minRow,
      m.char,
    );
    const chars = charMaps.get(m.char)?.get(cellKey(m.col, m.row));
    parts.push(moduleSvgAt(cx, cy, ctx, p.fillOpacity, chars));
  }
  parts.push('</g></svg>');

  return parts.join('');
}

/** Render one glyph with optional coordinate grid and vertical metrics. */
export function renderGlyphSvg(ch: string, ctx: RenderContext): string {
  const p = ctx.params;
  const coords = getGlyph(ch, p.colScale, p.rowScale);
  const minRow = 0;
  const maxRow = ROWS_TOTAL - 1;
  const cols = isBlank(ch)
    ? SPACE_WIDTH_COLS * Math.max(1, p.colScale)
    : scaledWidth(ch, p.colScale);
  const box = canvasBox(p, Math.max(cols - 1, 0), minRow, maxRow);

  const parts: string[] = [
    svgOpen(box.width, box.height, 1),
    `<rect width="100%" height="100%" fill="${p.background}"/>`,
  ];

  if (p.showGrid) {
    gridLines(parts, p, box, cols, minRow, maxRow);
    gridGhosts(parts, ctx, box, cols, minRow, maxRow);
  }
  if (p.showGuides) {
    glyphMetricGuides(parts, p, box, cols, minRow, maxRow);
  }

  const charMap =
    p.moduleType === MODULE_FONT ? fontCharMap(coords, ctx, ch) : new Map<number, string[]>();

  parts.push('<g>');
  for (const [col, row] of coords) {
    const [cx, cy] = transformedCenter(col, row, p, box.originX, box.originY, minRow, ch);
    parts.push(moduleSvgAt(cx, cy, ctx, p.fillOpacity, charMap.get(cellKey(col, row))));
  }
  parts.push('</g></svg>');

  return parts.join('');
}

/**
 * Outline segments of one module at a font-unit centre, ready for the OpenType
 * exporter. Returns an empty array when the module has nothing to draw.
 */
export function moduleOutlineSegments(
  cx: number,
  cy: number,
  ctx: RenderContext,
  scale: number,
  chars?: readonly string[],
): PathSegment[] {
  const p = ctx.params;

  // Outline space is Y-up while SVG rotation is Y-down, hence the negated angle.
  const applyRotation = (
    segments: PathSegment[],
    px: number,
    py: number,
  ): PathSegment[] =>
    Math.abs(p.moduleAngle) >= EPSILON
      ? transformSegments(segments, rotationAround(-p.moduleAngle, px, py))
      : segments;

  const oval = (): PathSegment[] =>
    applyRotation(ellipseSegments(cx, cy, p.rx * scale, p.ry * scale), cx, cy);

  if (p.moduleType === MODULE_OVAL) {
    return oval();
  }

  if (p.moduleType === MODULE_CUSTOM_SVG) {
    const shape = deserializeStamp(p.customSvgMarkup);
    if (!shape) {
      return oval();
    }
    const uniform = stampUniformScale(shape, p.rx * scale, p.ry * scale);
    return applyRotation(
      transformSegments(
        shape.segments,
        multiply(translation(cx, cy), scaling(uniform, -uniform)),
      ),
      cx,
      cy,
    );
  }

  if (p.moduleType === MODULE_FONT && chars && chars.length > 0) {
    const drawable = chars.filter((ch) => Boolean(ctx.fontPaths[ch]));
    if (drawable.length === 0) {
      return [];
    }
    const uniform = fontUniformScale(p, drawable.length) * scale;
    const out: PathSegment[] = [];
    drawable.forEach((ch, index) => {
      const dyFont = -symbolYOffset(index, drawable.length, p.ry) * scale;
      const placed = transformSegments(
        cachedFontSegments(ctx.fontPaths[ch]),
        multiply(translation(cx, cy + dyFont), scaling(uniform, uniform)),
      );
      out.push(...applyRotation(placed, cx, cy + dyFont));
    });
    return out;
  }

  return [];
}

const fontSegmentCache = new Map<string, PathSegment[]>();

function cachedFontSegments(data: string): PathSegment[] {
  const cached = fontSegmentCache.get(data);
  if (cached) {
    return cached;
  }
  const parsed = parsePathData(data);
  fontSegmentCache.set(data, parsed);
  return parsed;
}
