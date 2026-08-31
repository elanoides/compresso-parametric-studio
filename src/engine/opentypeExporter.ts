/**
 * Bake the current style into a real OpenType font.
 *
 * Every module of every glyph is flattened into cubic Bézier contours, so the
 * exported face looks exactly like the on-screen preview — including module
 * rotation, slant, glitch jitter and font-symbol stamps.
 *
 * opentype.js writes a CFF-flavoured sfnt (`OTTO`), which is why the artefact
 * is an `.otf`. Kerning is spliced in afterwards as GPOS plus a legacy `kern`.
 */

import * as opentype from 'opentype.js';

import { MODULE_FONT, type RenderContext, type StyleParams } from '../types/fontTypes';
import { BASELINE, BODY_TOP, GLYPH_CHARS, ROWS_TOTAL, getGlyph, glyphWidth } from './glyphs';
import {
  ellipseHalfExtents,
  fontCharMap,
  moduleCenterFontUnits,
  moduleOutlineSegments,
} from './geometry';
import { type KernPair, buildGposKernTable, buildLegacyKernTable, injectTables } from './sfnt';
import {
  DEFAULT_STYLE_NAME,
  FONT_FAMILY,
  glyphName,
  resolveStyleMetrics,
  styleSlug,
  windowsFamilyName,
} from './fontNaming';
import type { PathSegment } from './svgPath';

const UNITS_PER_EM = 1000;
/** The cap-height band maps to this many font units. */
const CAP_HEIGHT_FONT_UNITS = 750;

function segmentsToOpentypePath(segments: readonly PathSegment[]): opentype.Path {
  const path = new opentype.Path();
  const coord = (value: number): number => Math.round(value * 64) / 64;
  for (const seg of segments) {
    switch (seg.type) {
      case 'M':
        path.moveTo(coord(seg.x), coord(seg.y));
        break;
      case 'L':
        path.lineTo(coord(seg.x), coord(seg.y));
        break;
      case 'C':
        path.curveTo(
          coord(seg.x1),
          coord(seg.y1),
          coord(seg.x2),
          coord(seg.y2),
          coord(seg.x),
          coord(seg.y),
        );
        break;
      case 'Q':
        path.quadTo(coord(seg.x1), coord(seg.y1), coord(seg.x), coord(seg.y));
        break;
      case 'Z':
        path.close();
        break;
    }
  }
  return path;
}

/** Cap-height band to font-unit scale factor for the current spacing. */
export function fontUnitScale(p: StyleParams): number {
  const capSpan = Math.max((BASELINE - BODY_TOP) * p.stepY, 1);
  return CAP_HEIGHT_FONT_UNITS / capSpan;
}

function advanceWidthFor(ch: string, p: StyleParams, scale: number): number {
  const cols = glyphWidth(ch) * Math.max(1, p.colScale);
  return Math.max(1, Math.round((cols + p.letterSpacing) * p.stepX * scale));
}

interface BuiltGlyph {
  char: string;
  path: opentype.Path;
  advanceWidth: number;
  yMin: number;
  yMax: number;
}

function buildGlyphOutline(ch: string, ctx: RenderContext, scale: number): BuiltGlyph {
  const p = ctx.params;
  const coords = getGlyph(ch, p.colScale, p.rowScale);
  const charMap =
    p.moduleType === MODULE_FONT ? fontCharMap(coords, ctx, ch) : new Map<number, string[]>();

  const segments: PathSegment[] = [];
  const [halfWidth, halfHeight] = ellipseHalfExtents(
    p.rx * scale,
    p.ry * scale,
    p.moduleAngle,
  );

  let yMin = 0;
  let yMax = 0;
  let xMax = 0;

  for (const [col, row] of coords) {
    const [cx, cy] = moduleCenterFontUnits(col, row, p, scale, ch);
    segments.push(
      ...moduleOutlineSegments(cx, cy, ctx, scale, charMap.get(Math.trunc(col) * 4096 + row)),
    );
    yMin = Math.min(yMin, cy - halfHeight);
    yMax = Math.max(yMax, cy + halfHeight);
    xMax = Math.max(xMax, cx + halfWidth);
  }

  return {
    char: ch,
    path: segmentsToOpentypePath(segments),
    advanceWidth: Math.max(advanceWidthFor(ch, p, scale), Math.ceil(xMax), 1),
    yMin: Math.floor(yMin),
    yMax: Math.ceil(yMax),
  };
}

function notdefPath(): opentype.Path {
  const path = new opentype.Path();
  path.moveTo(50, 0);
  path.lineTo(50, 700);
  path.lineTo(450, 700);
  path.lineTo(450, 0);
  path.close();
  return path;
}

export interface FontBuildOptions {
  family?: string;
  styleName?: string;
}

export interface BuiltFont {
  binary: ArrayBuffer;
  filename: string;
  styleName: string;
  kernPairCount: number;
}

/** Compile the whole All-Caps alphabet into an OpenType binary. */
export function buildFontBinary(
  ctx: RenderContext,
  options: FontBuildOptions = {},
): BuiltFont {
  const p = ctx.params;
  const family = (options.family ?? FONT_FAMILY).trim() || FONT_FAMILY;
  const styleName = (options.styleName ?? DEFAULT_STYLE_NAME).trim() || DEFAULT_STYLE_NAME;
  const scale = fontUnitScale(p);
  const metrics = resolveStyleMetrics(styleName);

  const glyphs: opentype.Glyph[] = [
    new opentype.Glyph({ name: '.notdef', index: 0, advanceWidth: 500, path: notdefPath() }),
  ];

  // Space carries no ink but must exist so text sets correctly.
  glyphs.push(
    new opentype.Glyph({
      name: 'space',
      unicode: 32,
      unicodes: [32],
      index: 1,
      advanceWidth: advanceWidthFor(' ', p, scale),
      path: new opentype.Path(),
    }),
  );

  let outlineMin = 0;
  let outlineMax = 0;
  const glyphIndexByChar = new Map<string, number>();

  for (const ch of GLYPH_CHARS) {
    const built = buildGlyphOutline(ch, ctx, scale);
    outlineMin = Math.min(outlineMin, built.yMin);
    outlineMax = Math.max(outlineMax, built.yMax);

    const codePoint = ch.codePointAt(0)!;
    const unicodes = [codePoint];
    const lower = ch.toLowerCase();
    if (lower !== ch) {
      unicodes.push(lower.codePointAt(0)!);
    }

    const index = glyphs.length;
    glyphIndexByChar.set(ch, index);
    glyphs.push(
      new opentype.Glyph({
        name: glyphName(ch),
        unicode: codePoint,
        unicodes,
        index,
        advanceWidth: built.advanceWidth,
        path: built.path,
      }),
    );
  }

  const ascender = Math.max(
    Math.ceil(BASELINE * p.stepY * scale + p.ry * scale),
    outlineMax,
    1,
  );
  const descender = Math.min(
    Math.floor((BASELINE - (ROWS_TOTAL - 1)) * p.stepY * scale - p.ry * scale),
    outlineMin,
    -1,
  );

  const font = new opentype.Font({
    familyName: windowsFamilyName(family, styleName),
    styleName,
    unitsPerEm: UNITS_PER_EM,
    ascender,
    descender,
    glyphs,
    weightClass: metrics.weightClass,
    widthClass: metrics.widthClass,
    fsSelection: metrics.fsSelection,
    italicAngle: metrics.italic ? -Math.abs(p.slantAngle || 12) : 0,
    version: 'Version 2.000',
    manufacturer: 'Compresso Parametric Font Studio',
    designer: 'Compresso Parametric Font Studio',
    description: `Generated by Compresso Parametric Font Studio — ${family} ${styleName}`,
  });

  const kernPairs = resolveKernPairs(p, scale, glyphIndexByChar);
  let binary = font.toArrayBuffer();

  const extras: Array<{ tag: string; data: Uint8Array }> = [];
  const gpos = buildGposKernTable(kernPairs);
  if (gpos) {
    extras.push({ tag: 'GPOS', data: gpos });
  }
  const legacy = buildLegacyKernTable(kernPairs);
  if (legacy) {
    extras.push({ tag: 'kern', data: legacy });
  }
  if (extras.length > 0) {
    binary = injectTables(binary, extras);
  }

  return {
    binary,
    filename: `${styleSlug(family)}-${styleSlug(styleName)}.otf`,
    styleName,
    kernPairCount: kernPairs.length,
  };
}

/** Convert studio kerning (grid columns) into font-unit GPOS adjustments. */
function resolveKernPairs(
  p: StyleParams,
  scale: number,
  glyphIndexByChar: ReadonlyMap<string, number>,
): KernPair[] {
  const out: KernPair[] = [];
  const seen = new Set<string>();

  for (const [pair, delta] of Object.entries(p.kerningPairs)) {
    if ([...pair].length !== 2) {
      continue;
    }
    const [leftChar, rightChar] = [...pair];
    const left = glyphIndexByChar.get(leftChar);
    const right = glyphIndexByChar.get(rightChar);
    if (left === undefined || right === undefined) {
      continue;
    }
    const value = Math.round(delta * p.stepX * scale);
    if (value === 0) {
      continue;
    }
    const key = `${left}/${right}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    out.push({ left, right, value });
  }

  return out;
}
