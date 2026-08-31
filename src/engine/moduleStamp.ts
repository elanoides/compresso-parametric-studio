/**
 * Custom SVG module stamps: parse an uploaded file into flat outline segments,
 * centre them on the origin and record their aspect so the renderer and the
 * font exporter can both fit the stamp into an rx/ry cell.
 */

import {
  IDENTITY,
  type Matrix,
  type PathSegment,
  ellipseSegments,
  multiply,
  parsePathData,
  polySegments,
  rectSegments,
  rotation,
  scaling,
  segmentsBBox,
  segmentsToPathData,
  transformSegments,
  translation,
} from './svgPath';

/** A stamp normalized so its bounding box is centred on `(0, 0)`. */
export interface StampShape {
  segments: readonly PathSegment[];
  /** Bounding-box width in the stamp's own units. */
  width: number;
  /** Bounding-box height in the stamp's own units. */
  height: number;
}

const TRANSFORM_RE = /(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)/g;
const NUMBER_RE = /[+-]?(?:\d*\.\d+|\d+\.?)(?:[eE][+-]?\d+)?/g;

function parseNumbers(raw: string): number[] {
  const found = raw.match(NUMBER_RE);
  return found ? found.map((n) => Number.parseFloat(n)) : [];
}

function skewX(degrees: number): Matrix {
  return [1, 0, Math.tan((degrees * Math.PI) / 180), 1, 0, 0];
}

function skewY(degrees: number): Matrix {
  return [1, Math.tan((degrees * Math.PI) / 180), 0, 1, 0, 0];
}

/** Parse an SVG `transform` attribute into a single matrix. */
export function parseTransformAttribute(value: string | null): Matrix {
  if (!value) {
    return IDENTITY;
  }
  let result = IDENTITY;
  TRANSFORM_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = TRANSFORM_RE.exec(value)) !== null) {
    const args = parseNumbers(match[2]);
    switch (match[1]) {
      case 'matrix':
        if (args.length >= 6) {
          result = multiply(result, [args[0], args[1], args[2], args[3], args[4], args[5]]);
        }
        break;
      case 'translate':
        result = multiply(result, translation(args[0] ?? 0, args[1] ?? 0));
        break;
      case 'scale': {
        const sx = args[0] ?? 1;
        result = multiply(result, scaling(sx, args[1] ?? sx));
        break;
      }
      case 'rotate': {
        const angle = args[0] ?? 0;
        if (args.length >= 3) {
          result = multiply(
            result,
            multiply(
              multiply(translation(args[1], args[2]), rotation(angle)),
              translation(-args[1], -args[2]),
            ),
          );
        } else {
          result = multiply(result, rotation(angle));
        }
        break;
      }
      case 'skewX':
        result = multiply(result, skewX(args[0] ?? 0));
        break;
      case 'skewY':
        result = multiply(result, skewY(args[0] ?? 0));
        break;
      default:
        break;
    }
  }
  return result;
}

function numberAttr(element: Element, name: string, fallback = 0): number {
  const raw = element.getAttribute(name);
  if (raw === null) {
    return fallback;
  }
  const value = Number.parseFloat(raw);
  return Number.isFinite(value) ? value : fallback;
}

function elementSegments(element: Element): PathSegment[] {
  switch (element.tagName.toLowerCase()) {
    case 'path': {
      const d = element.getAttribute('d');
      return d && d.trim() ? parsePathData(d) : [];
    }
    case 'circle': {
      const r = numberAttr(element, 'r');
      return r > 0
        ? ellipseSegments(numberAttr(element, 'cx'), numberAttr(element, 'cy'), r, r)
        : [];
    }
    case 'ellipse': {
      const rx = numberAttr(element, 'rx');
      const ry = numberAttr(element, 'ry');
      return rx > 0 && ry > 0
        ? ellipseSegments(numberAttr(element, 'cx'), numberAttr(element, 'cy'), rx, ry)
        : [];
    }
    case 'rect': {
      const width = numberAttr(element, 'width');
      const height = numberAttr(element, 'height');
      return width > 0 && height > 0
        ? rectSegments(numberAttr(element, 'x'), numberAttr(element, 'y'), width, height)
        : [];
    }
    case 'line':
      return [
        { type: 'M', x: numberAttr(element, 'x1'), y: numberAttr(element, 'y1') },
        { type: 'L', x: numberAttr(element, 'x2'), y: numberAttr(element, 'y2') },
      ];
    case 'polyline':
      return polySegments(element.getAttribute('points') ?? '', false);
    case 'polygon':
      return polySegments(element.getAttribute('points') ?? '', true);
    default:
      return [];
  }
}

function collect(element: Element, parentMatrix: Matrix, out: PathSegment[]): void {
  const matrix = multiply(
    parentMatrix,
    parseTransformAttribute(element.getAttribute('transform')),
  );
  const own = elementSegments(element);
  if (own.length > 0) {
    out.push(...transformSegments(own, matrix));
  }
  for (const child of Array.from(element.children)) {
    collect(child, matrix, out);
  }
}

/**
 * Parse SVG markup into a centred stamp shape.
 * Throws when the file contains no drawable geometry.
 */
export function parseCustomSvg(markup: string): StampShape {
  const doc = new DOMParser().parseFromString(markup, 'image/svg+xml');
  const parseError = doc.querySelector('parsererror');
  if (parseError) {
    throw new Error('Файл не является корректным SVG');
  }
  const root = doc.documentElement;
  if (!root || root.tagName.toLowerCase() !== 'svg') {
    throw new Error('Корневой элемент должен быть <svg>');
  }

  const segments: PathSegment[] = [];
  for (const child of Array.from(root.children)) {
    collect(child, IDENTITY, segments);
  }
  if (segments.length === 0) {
    throw new Error('В SVG не найдено фигур (path, circle, ellipse, rect, polygon)');
  }

  const bbox = segmentsBBox(segments);
  const width = Math.max(bbox.x1 - bbox.x0, 1e-6);
  const height = Math.max(bbox.y1 - bbox.y0, 1e-6);
  const centreX = (bbox.x0 + bbox.x1) / 2;
  const centreY = (bbox.y0 + bbox.y1) / 2;

  return {
    segments: transformSegments(segments, translation(-centreX, -centreY)),
    width,
    height,
  };
}

/** Serialized form kept inside a preset so styles stay self-contained. */
export interface SerializedStamp {
  width: number;
  height: number;
  pathData: string;
}

export function serializeStamp(shape: StampShape): string {
  const payload: SerializedStamp = {
    width: shape.width,
    height: shape.height,
    pathData: segmentsToPathData(shape.segments),
  };
  return JSON.stringify(payload);
}

const stampCache = new Map<string, StampShape | null>();

/** Rebuild a stamp from its serialized preset form (memoized). */
export function deserializeStamp(raw: string): StampShape | null {
  if (!raw) {
    return null;
  }
  if (stampCache.has(raw)) {
    return stampCache.get(raw) ?? null;
  }
  let shape: StampShape | null = null;
  try {
    const payload = JSON.parse(raw) as SerializedStamp;
    if (payload.pathData) {
      shape = {
        segments: parsePathData(payload.pathData),
        width: Math.max(payload.width, 1e-6),
        height: Math.max(payload.height, 1e-6),
      };
    }
  } catch {
    shape = null;
  }
  stampCache.set(raw, shape);
  return shape;
}

/** Uniform scale that fits the stamp inside the module's rx/ry box. */
export function stampUniformScale(shape: StampShape, rx: number, ry: number): number {
  return Math.min((2 * rx) / shape.width, (2 * ry) / shape.height);
}
