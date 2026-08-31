/**
 * SVG path and shape geometry: parsing, affine transforms, tight bounding
 * boxes and serialization. Shared by the live SVG renderer and the OpenType
 * exporter so an uploaded stamp bakes into outlines exactly as it previews.
 */

export type PathSegment =
  | { readonly type: 'M'; readonly x: number; readonly y: number }
  | { readonly type: 'L'; readonly x: number; readonly y: number }
  | {
      readonly type: 'C';
      readonly x1: number;
      readonly y1: number;
      readonly x2: number;
      readonly y2: number;
      readonly x: number;
      readonly y: number;
    }
  | {
      readonly type: 'Q';
      readonly x1: number;
      readonly y1: number;
      readonly x: number;
      readonly y: number;
    }
  | { readonly type: 'Z' };

/** Affine matrix `[a, b, c, d, e, f]` mapping `(x,y)` to `(ax+cy+e, bx+dy+f)`. */
export type Matrix = readonly [number, number, number, number, number, number];

export const IDENTITY: Matrix = [1, 0, 0, 1, 0, 0];

export function multiply(outer: Matrix, inner: Matrix): Matrix {
  const [a1, b1, c1, d1, e1, f1] = outer;
  const [a2, b2, c2, d2, e2, f2] = inner;
  return [
    a1 * a2 + c1 * b2,
    b1 * a2 + d1 * b2,
    a1 * c2 + c1 * d2,
    b1 * c2 + d1 * d2,
    a1 * e2 + c1 * f2 + e1,
    b1 * e2 + d1 * f2 + f1,
  ];
}

export function translation(tx: number, ty: number): Matrix {
  return [1, 0, 0, 1, tx, ty];
}

export function scaling(sx: number, sy: number): Matrix {
  return [sx, 0, 0, sy, 0, 0];
}

export function rotation(degrees: number): Matrix {
  const rad = (degrees * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  return [cos, sin, -sin, cos, 0, 0];
}

/** Rotate by `degrees` around `(cx, cy)`. */
export function rotationAround(degrees: number, cx: number, cy: number): Matrix {
  return multiply(multiply(translation(cx, cy), rotation(degrees)), translation(-cx, -cy));
}

function applyPoint(m: Matrix, x: number, y: number): [number, number] {
  return [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];
}

export function transformSegments(
  segments: readonly PathSegment[],
  m: Matrix,
): PathSegment[] {
  const out: PathSegment[] = [];
  for (const seg of segments) {
    switch (seg.type) {
      case 'M': {
        const [x, y] = applyPoint(m, seg.x, seg.y);
        out.push({ type: 'M', x, y });
        break;
      }
      case 'L': {
        const [x, y] = applyPoint(m, seg.x, seg.y);
        out.push({ type: 'L', x, y });
        break;
      }
      case 'C': {
        const [x1, y1] = applyPoint(m, seg.x1, seg.y1);
        const [x2, y2] = applyPoint(m, seg.x2, seg.y2);
        const [x, y] = applyPoint(m, seg.x, seg.y);
        out.push({ type: 'C', x1, y1, x2, y2, x, y });
        break;
      }
      case 'Q': {
        const [x1, y1] = applyPoint(m, seg.x1, seg.y1);
        const [x, y] = applyPoint(m, seg.x, seg.y);
        out.push({ type: 'Q', x1, y1, x, y });
        break;
      }
      case 'Z':
        out.push(seg);
        break;
    }
  }
  return out;
}

function round(value: number, precision: number): string {
  const factor = 10 ** precision;
  const rounded = Math.round(value * factor) / factor;
  return Object.is(rounded, -0) ? '0' : String(rounded);
}

export function segmentsToPathData(
  segments: readonly PathSegment[],
  precision = 4,
): string {
  const parts: string[] = [];
  for (const seg of segments) {
    switch (seg.type) {
      case 'M':
        parts.push(`M${round(seg.x, precision)} ${round(seg.y, precision)}`);
        break;
      case 'L':
        parts.push(`L${round(seg.x, precision)} ${round(seg.y, precision)}`);
        break;
      case 'C':
        parts.push(
          `C${round(seg.x1, precision)} ${round(seg.y1, precision)} ` +
            `${round(seg.x2, precision)} ${round(seg.y2, precision)} ` +
            `${round(seg.x, precision)} ${round(seg.y, precision)}`,
        );
        break;
      case 'Q':
        parts.push(
          `Q${round(seg.x1, precision)} ${round(seg.y1, precision)} ` +
            `${round(seg.x, precision)} ${round(seg.y, precision)}`,
        );
        break;
      case 'Z':
        parts.push('Z');
        break;
    }
  }
  return parts.join(' ');
}

export interface BBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

function cubicExtrema(p0: number, p1: number, p2: number, p3: number): number[] {
  // Derivative of a cubic Bézier is a quadratic: at² + bt + c.
  const a = 3 * (-p0 + 3 * p1 - 3 * p2 + p3);
  const b = 6 * (p0 - 2 * p1 + p2);
  const c = 3 * (p1 - p0);
  const roots: number[] = [];

  if (Math.abs(a) < 1e-12) {
    if (Math.abs(b) > 1e-12) {
      roots.push(-c / b);
    }
  } else {
    const disc = b * b - 4 * a * c;
    if (disc >= 0) {
      const sq = Math.sqrt(disc);
      roots.push((-b + sq) / (2 * a), (-b - sq) / (2 * a));
    }
  }

  const values: number[] = [];
  for (const t of roots) {
    if (t > 0 && t < 1) {
      const mt = 1 - t;
      values.push(
        mt * mt * mt * p0 + 3 * mt * mt * t * p1 + 3 * mt * t * t * p2 + t * t * t * p3,
      );
    }
  }
  return values;
}

function quadExtrema(p0: number, p1: number, p2: number): number[] {
  const denom = p0 - 2 * p1 + p2;
  if (Math.abs(denom) < 1e-12) {
    return [];
  }
  const t = (p0 - p1) / denom;
  if (t <= 0 || t >= 1) {
    return [];
  }
  const mt = 1 - t;
  return [mt * mt * p0 + 2 * mt * t * p1 + t * t * p2];
}

/** Tight bounding box (curve extrema included, not just control points). */
export function segmentsBBox(segments: readonly PathSegment[]): BBox {
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  let curX = 0;
  let curY = 0;

  const include = (x: number, y: number): void => {
    if (x < x0) x0 = x;
    if (y < y0) y0 = y;
    if (x > x1) x1 = x;
    if (y > y1) y1 = y;
  };

  for (const seg of segments) {
    switch (seg.type) {
      case 'M':
      case 'L':
        include(seg.x, seg.y);
        curX = seg.x;
        curY = seg.y;
        break;
      case 'C':
        include(curX, curY);
        include(seg.x, seg.y);
        for (const v of cubicExtrema(curX, seg.x1, seg.x2, seg.x)) {
          include(v, curY);
        }
        for (const v of cubicExtrema(curY, seg.y1, seg.y2, seg.y)) {
          include(curX, v);
        }
        curX = seg.x;
        curY = seg.y;
        break;
      case 'Q':
        include(curX, curY);
        include(seg.x, seg.y);
        for (const v of quadExtrema(curX, seg.x1, seg.x)) {
          include(v, curY);
        }
        for (const v of quadExtrema(curY, seg.y1, seg.y)) {
          include(curX, v);
        }
        curX = seg.x;
        curY = seg.y;
        break;
      case 'Z':
        break;
    }
  }

  if (!Number.isFinite(x0)) {
    return { x0: -1, y0: -1, x1: 1, y1: 1 };
  }
  return { x0, y0, x1, y1 };
}

/* ------------------------------------------------------------------ *
 * Path data parsing
 * ------------------------------------------------------------------ */

const NUMBER_RE = /[+-]?(?:\d*\.\d+|\d+\.?)(?:[eE][+-]?\d+)?/g;

function tokenize(d: string): Array<{ cmd: string; args: number[] }> {
  const out: Array<{ cmd: string; args: number[] }> = [];
  const commandRe = /([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)/g;
  let match: RegExpExecArray | null;
  while ((match = commandRe.exec(d)) !== null) {
    const args: number[] = [];
    const numbers = match[2].match(NUMBER_RE);
    if (numbers) {
      for (const n of numbers) {
        args.push(Number.parseFloat(n));
      }
    }
    out.push({ cmd: match[1], args });
  }
  return out;
}

/** Convert one SVG elliptical arc to a chain of cubic Béziers. */
function arcToCubics(
  x0: number,
  y0: number,
  rxIn: number,
  ryIn: number,
  angleDeg: number,
  largeArc: boolean,
  sweep: boolean,
  x: number,
  y: number,
): PathSegment[] {
  if (x0 === x && y0 === y) {
    return [];
  }
  let rx = Math.abs(rxIn);
  let ry = Math.abs(ryIn);
  if (rx < 1e-12 || ry < 1e-12) {
    return [{ type: 'L', x, y }];
  }

  const phi = (angleDeg * Math.PI) / 180;
  const cosPhi = Math.cos(phi);
  const sinPhi = Math.sin(phi);

  const dx2 = (x0 - x) / 2;
  const dy2 = (y0 - y) / 2;
  const x1p = cosPhi * dx2 + sinPhi * dy2;
  const y1p = -sinPhi * dx2 + cosPhi * dy2;

  const lambda = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry);
  if (lambda > 1) {
    const scale = Math.sqrt(lambda);
    rx *= scale;
    ry *= scale;
  }

  const sign = largeArc === sweep ? -1 : 1;
  const numerator =
    rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p;
  const denominator = rx * rx * y1p * y1p + ry * ry * x1p * x1p;
  const coef = sign * Math.sqrt(Math.max(0, numerator / denominator));

  const cxp = (coef * rx * y1p) / ry;
  const cyp = (-coef * ry * x1p) / rx;
  const cx = cosPhi * cxp - sinPhi * cyp + (x0 + x) / 2;
  const cy = sinPhi * cxp + cosPhi * cyp + (y0 + y) / 2;

  const angle = (ux: number, uy: number, vx: number, vy: number): number => {
    const dot = ux * vx + uy * vy;
    const len = Math.sqrt((ux * ux + uy * uy) * (vx * vx + vy * vy));
    let value = Math.acos(Math.min(1, Math.max(-1, dot / len)));
    if (ux * vy - uy * vx < 0) {
      value = -value;
    }
    return value;
  };

  const theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry);
  let deltaTheta = angle(
    (x1p - cxp) / rx,
    (y1p - cyp) / ry,
    (-x1p - cxp) / rx,
    (-y1p - cyp) / ry,
  );

  if (!sweep && deltaTheta > 0) {
    deltaTheta -= 2 * Math.PI;
  } else if (sweep && deltaTheta < 0) {
    deltaTheta += 2 * Math.PI;
  }

  const segmentCount = Math.max(1, Math.ceil(Math.abs(deltaTheta) / (Math.PI / 2)));
  const delta = deltaTheta / segmentCount;
  const alpha = (4 / 3) * Math.tan(delta / 4);

  const out: PathSegment[] = [];
  let theta = theta1;
  let px = x0;
  let py = y0;

  for (let i = 0; i < segmentCount; i += 1) {
    const thetaNext = theta + delta;

    const cosT = Math.cos(theta);
    const sinT = Math.sin(theta);
    const cosN = Math.cos(thetaNext);
    const sinN = Math.sin(thetaNext);

    const dxdt1 = -rx * sinT;
    const dydt1 = ry * cosT;
    const dxdt2 = -rx * sinN;
    const dydt2 = ry * cosN;

    const ex = cx + cosPhi * (rx * cosN) - sinPhi * (ry * sinN);
    const ey = cy + sinPhi * (rx * cosN) + cosPhi * (ry * sinN);

    const c1x = px + alpha * (cosPhi * dxdt1 - sinPhi * dydt1);
    const c1y = py + alpha * (sinPhi * dxdt1 + cosPhi * dydt1);
    const c2x = ex - alpha * (cosPhi * dxdt2 - sinPhi * dydt2);
    const c2y = ey - alpha * (sinPhi * dxdt2 + cosPhi * dydt2);

    out.push({ type: 'C', x1: c1x, y1: c1y, x2: c2x, y2: c2y, x: ex, y: ey });

    theta = thetaNext;
    px = ex;
    py = ey;
  }

  return out;
}

/**
 * Parse SVG path data into absolute `M`/`L`/`C`/`Q`/`Z` segments.
 * Relative commands, shorthands and arcs are all resolved.
 */
export function parsePathData(d: string): PathSegment[] {
  const out: PathSegment[] = [];
  let curX = 0;
  let curY = 0;
  let startX = 0;
  let startY = 0;
  let lastCubicCtrlX = 0;
  let lastCubicCtrlY = 0;
  let lastQuadCtrlX = 0;
  let lastQuadCtrlY = 0;
  let prevType = '';

  for (const { cmd, args } of tokenize(d)) {
    const relative = cmd === cmd.toLowerCase() && cmd !== 'Z' && cmd !== 'z';
    const upper = cmd.toUpperCase();

    if (upper === 'Z') {
      out.push({ type: 'Z' });
      curX = startX;
      curY = startY;
      prevType = 'Z';
      continue;
    }

    const stride =
      upper === 'M' || upper === 'L' || upper === 'T'
        ? 2
        : upper === 'H' || upper === 'V'
          ? 1
          : upper === 'C'
            ? 6
            : upper === 'S' || upper === 'Q'
              ? 4
              : 7;

    for (let i = 0; i + stride <= args.length; i += stride) {
      const a = args.slice(i, i + stride);
      const baseX = relative ? curX : 0;
      const baseY = relative ? curY : 0;

      switch (upper) {
        case 'M': {
          const x = a[0] + baseX;
          const y = a[1] + baseY;
          // Subsequent coordinate pairs after a moveto are implicit linetos.
          if (i === 0) {
            out.push({ type: 'M', x, y });
            startX = x;
            startY = y;
          } else {
            out.push({ type: 'L', x, y });
          }
          curX = x;
          curY = y;
          break;
        }
        case 'L': {
          const x = a[0] + baseX;
          const y = a[1] + baseY;
          out.push({ type: 'L', x, y });
          curX = x;
          curY = y;
          break;
        }
        case 'H': {
          const x = a[0] + baseX;
          out.push({ type: 'L', x, y: curY });
          curX = x;
          break;
        }
        case 'V': {
          const y = a[0] + baseY;
          out.push({ type: 'L', x: curX, y });
          curY = y;
          break;
        }
        case 'C': {
          const x1 = a[0] + baseX;
          const y1 = a[1] + baseY;
          const x2 = a[2] + baseX;
          const y2 = a[3] + baseY;
          const x = a[4] + baseX;
          const y = a[5] + baseY;
          out.push({ type: 'C', x1, y1, x2, y2, x, y });
          lastCubicCtrlX = x2;
          lastCubicCtrlY = y2;
          curX = x;
          curY = y;
          break;
        }
        case 'S': {
          const smooth = prevType === 'C' || prevType === 'S';
          const x1 = smooth ? 2 * curX - lastCubicCtrlX : curX;
          const y1 = smooth ? 2 * curY - lastCubicCtrlY : curY;
          const x2 = a[0] + baseX;
          const y2 = a[1] + baseY;
          const x = a[2] + baseX;
          const y = a[3] + baseY;
          out.push({ type: 'C', x1, y1, x2, y2, x, y });
          lastCubicCtrlX = x2;
          lastCubicCtrlY = y2;
          curX = x;
          curY = y;
          break;
        }
        case 'Q': {
          const x1 = a[0] + baseX;
          const y1 = a[1] + baseY;
          const x = a[2] + baseX;
          const y = a[3] + baseY;
          out.push({ type: 'Q', x1, y1, x, y });
          lastQuadCtrlX = x1;
          lastQuadCtrlY = y1;
          curX = x;
          curY = y;
          break;
        }
        case 'T': {
          const smooth = prevType === 'Q' || prevType === 'T';
          const x1 = smooth ? 2 * curX - lastQuadCtrlX : curX;
          const y1 = smooth ? 2 * curY - lastQuadCtrlY : curY;
          const x = a[0] + baseX;
          const y = a[1] + baseY;
          out.push({ type: 'Q', x1, y1, x, y });
          lastQuadCtrlX = x1;
          lastQuadCtrlY = y1;
          curX = x;
          curY = y;
          break;
        }
        case 'A': {
          const x = a[5] + baseX;
          const y = a[6] + baseY;
          out.push(
            ...arcToCubics(curX, curY, a[0], a[1], a[2], a[3] !== 0, a[4] !== 0, x, y),
          );
          curX = x;
          curY = y;
          break;
        }
        default:
          break;
      }

      prevType = upper;
    }
  }

  return out;
}

/* ------------------------------------------------------------------ *
 * Primitive shapes
 * ------------------------------------------------------------------ */

/** Circular-arc magic constant for a 4-segment Bézier ellipse. */
const KAPPA = 0.5522847498307936;

export function ellipseSegments(
  cx: number,
  cy: number,
  rx: number,
  ry: number,
): PathSegment[] {
  const ox = rx * KAPPA;
  const oy = ry * KAPPA;
  return [
    { type: 'M', x: cx + rx, y: cy },
    { type: 'C', x1: cx + rx, y1: cy + oy, x2: cx + ox, y2: cy + ry, x: cx, y: cy + ry },
    { type: 'C', x1: cx - ox, y1: cy + ry, x2: cx - rx, y2: cy + oy, x: cx - rx, y: cy },
    { type: 'C', x1: cx - rx, y1: cy - oy, x2: cx - ox, y2: cy - ry, x: cx, y: cy - ry },
    { type: 'C', x1: cx + ox, y1: cy - ry, x2: cx + rx, y2: cy - oy, x: cx + rx, y: cy },
    { type: 'Z' },
  ];
}

export function rectSegments(
  x: number,
  y: number,
  width: number,
  height: number,
): PathSegment[] {
  return [
    { type: 'M', x, y },
    { type: 'L', x: x + width, y },
    { type: 'L', x: x + width, y: y + height },
    { type: 'L', x, y: y + height },
    { type: 'Z' },
  ];
}

export function polySegments(points: string, closed: boolean): PathSegment[] {
  const numbers = points.match(NUMBER_RE);
  if (!numbers || numbers.length < 4) {
    return [];
  }
  const out: PathSegment[] = [];
  for (let i = 0; i + 1 < numbers.length; i += 2) {
    const x = Number.parseFloat(numbers[i]);
    const y = Number.parseFloat(numbers[i + 1]);
    out.push(i === 0 ? { type: 'M', x, y } : { type: 'L', x, y });
  }
  if (closed) {
    out.push({ type: 'Z' });
  }
  return out;
}
