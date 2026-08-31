/** Core domain types for the CRT Parametric Font Studio engine. */

/** One module slot on the 28-row grid: `[column, row]`. */
export type GridCoord = readonly [number, number];

/** All module slots of a single glyph. */
export type GlyphMatrix = readonly GridCoord[];

export const MODULE_OVAL = 'oval';
export const MODULE_CUSTOM_SVG = 'custom_svg';
export const MODULE_FONT = 'font_symbols';

export type ModuleType =
  | typeof MODULE_OVAL
  | typeof MODULE_CUSTOM_SVG
  | typeof MODULE_FONT;

export const FILL_ORDER_COLUMNS = 'columns';
export const FILL_ORDER_ROWS = 'rows';

export type FillOrder = typeof FILL_ORDER_COLUMNS | typeof FILL_ORDER_ROWS;

/** Kerning deltas in grid-column units, keyed by a two-character pair. */
export type KerningPairs = Readonly<Record<string, number>>;

/**
 * Every parameter that defines one style (начертание).
 * This object is what gets stored in a preset, serialized to JSON and
 * fed to the geometry engine.
 */
export interface StyleParams {
  // Module geometry
  moduleType: ModuleType;
  rx: number;
  ry: number;
  strokeWidth: number;
  fillOpacity: number;
  moduleAngle: number;

  // Custom SVG module
  customSvgMarkup: string;
  customSvgName: string;

  // Font-symbol module
  moduleFontSubfamily: string;
  moduleFontWeight: string;
  moduleFontChars: string;
  moduleFontFillOrder: FillOrder;
  moduleFontRandomize: boolean;
  moduleFontSymbolsPerModule: number;

  // Spacing & density
  stepX: number;
  stepY: number;
  colScale: number;
  rowScale: number;
  letterSpacing: number;

  // Deformations & FX
  slantAngle: number;
  jitterX: number;
  rowJitter: number;
  seed: number;

  // Colour & guides
  fill: string;
  stroke: string;
  background: string;
  guideColor: string;
  gridColor: string;
  showGuides: boolean;
  showGrid: boolean;

  // Kerning
  kerningPairs: KerningPairs;
}

/** A named style in the preset library. */
export interface Preset {
  name: string;
  params: StyleParams;
}

export type PresetLibrary = Readonly<Record<string, StyleParams>>;

/** On-disk JSON shape for preset import / export. */
export interface PresetFilePayload {
  format: string;
  active: string | null;
  presets: Record<string, Partial<StyleParams>>;
}

/**
 * Resolved render inputs: style params plus the outline paths needed to draw
 * font-symbol modules. Paths are normalized to a unit box, Y-up.
 */
export interface RenderContext {
  params: StyleParams;
  /** character -> SVG path `d` in a 1×1 box centred on the origin, Y-up. */
  fontPaths: Readonly<Record<string, string>>;
  /** Characters available in the currently selected module font. */
  fontAlphabet: string;
}

/** Canvas geometry for one rendered SVG. */
export interface CanvasBox {
  width: number;
  height: number;
  originX: number;
  originY: number;
}

/** One placed module: absolute column, row and the glyph it belongs to. */
export interface PlacedModule {
  col: number;
  row: number;
  char: string;
}

export interface TextLayout {
  modules: PlacedModule[];
  maxCol: number;
  minRow: number;
  maxRow: number;
}

export type TabId = 'word' | 'glyph' | 'styles';
