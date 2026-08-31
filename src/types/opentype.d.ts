/**
 * Minimal ambient types for opentype.js 2.x, which ships no declarations.
 * Only the surface this project uses is declared.
 */
declare module 'opentype.js' {
  export interface PathCommandMove {
    type: 'M';
    x: number;
    y: number;
  }
  export interface PathCommandLine {
    type: 'L';
    x: number;
    y: number;
  }
  export interface PathCommandCurve {
    type: 'C';
    x1: number;
    y1: number;
    x2: number;
    y2: number;
    x: number;
    y: number;
  }
  export interface PathCommandQuad {
    type: 'Q';
    x1: number;
    y1: number;
    x: number;
    y: number;
  }
  export interface PathCommandClose {
    type: 'Z';
  }

  export type PathCommand =
    | PathCommandMove
    | PathCommandLine
    | PathCommandCurve
    | PathCommandQuad
    | PathCommandClose;

  export class Path {
    commands: PathCommand[];
    fill: string | null;
    stroke: string | null;
    strokeWidth: number;
    moveTo(x: number, y: number): void;
    lineTo(x: number, y: number): void;
    curveTo(
      x1: number,
      y1: number,
      x2: number,
      y2: number,
      x: number,
      y: number,
    ): void;
    quadTo(x1: number, y1: number, x: number, y: number): void;
    close(): void;
    closePath(): void;
    extend(pathOrCommands: Path | PathCommand[]): void;
    toPathData(decimalPlaces?: number): string;
  }

  export interface GlyphOptions {
    name?: string;
    unicode?: number;
    unicodes?: number[];
    index?: number;
    advanceWidth?: number;
    leftSideBearing?: number;
    path?: Path;
  }

  export class Glyph {
    constructor(options: GlyphOptions);
    name: string | null;
    unicode?: number;
    unicodes: number[];
    index: number;
    advanceWidth: number;
    path: Path;
    getBoundingBox(): { x1: number; y1: number; x2: number; y2: number };
  }

  export interface GlyphSet {
    length: number;
    get(index: number): Glyph;
  }

  export interface FontOptions {
    familyName: string;
    styleName: string;
    unitsPerEm: number;
    ascender: number;
    descender: number;
    glyphs: Glyph[];
    designer?: string;
    designerURL?: string;
    manufacturer?: string;
    manufacturerURL?: string;
    license?: string;
    licenseURL?: string;
    version?: string;
    description?: string;
    copyright?: string;
    trademark?: string;
    weightClass?: number;
    widthClass?: number;
    fsSelection?: number;
    italicAngle?: number;
    createdTimestamp?: number;
    tables?: Record<string, unknown>;
  }

  export class Font {
    constructor(options: FontOptions);
    unitsPerEm: number;
    ascender: number;
    descender: number;
    glyphs: GlyphSet;
    tables: Record<string, unknown>;
    names: Record<string, unknown>;
    numGlyphs: number;
    charToGlyph(ch: string): Glyph;
    charToGlyphIndex(ch: string): number;
    hasChar(ch: string): boolean;
    getEnglishName(name: string): string;
    toArrayBuffer(): ArrayBuffer;
  }

  export function parse(buffer: ArrayBuffer, options?: Record<string, unknown>): Font;
}
