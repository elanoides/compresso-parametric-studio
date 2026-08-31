/** Factory style library and preset (de)serialization. */

import {
  FILL_ORDER_COLUMNS,
  MODULE_OVAL,
  type PresetFilePayload,
  type PresetLibrary,
  type StyleParams,
} from '../types/fontTypes';

export const PRESET_FILE_FORMAT = 'crt-font-studio-presets-v3';

/** The reference style — every other preset is a delta on top of this. */
export const REGULAR_PARAMS: StyleParams = {
  moduleType: MODULE_OVAL,
  rx: 30,
  ry: 10,
  strokeWidth: 0,
  fillOpacity: 1,
  moduleAngle: 0,

  customSvgMarkup: '',
  customSvgName: '',

  moduleFontSubfamily: 'SB Sans Display',
  moduleFontWeight: 'Regular',
  moduleFontChars: '',
  moduleFontFillOrder: FILL_ORDER_COLUMNS,
  moduleFontRandomize: false,
  moduleFontSymbolsPerModule: 1,

  stepX: 38.5,
  stepY: 16,
  colScale: 1,
  rowScale: 1,
  letterSpacing: 1,

  slantAngle: 0,
  jitterX: 0,
  rowJitter: 0,
  seed: 0,

  fill: '#FFFFFF',
  stroke: '#FFFFFF',
  background: '#000000',
  guideColor: '#FF6B4A',
  gridColor: '#4A6A4A',
  showGuides: false,
  showGrid: false,

  kerningPairs: {},
};

export const DEFAULT_PRESETS: PresetLibrary = {
  Regular: { ...REGULAR_PARAMS },
  'Italic Slant': { ...REGULAR_PARAMS, slantAngle: 14 },
  'Diamond 45°': { ...REGULAR_PARAMS, moduleAngle: 45, stepX: 36, stepY: 15 },
  'Glitch CRT': {
    ...REGULAR_PARAMS,
    jitterX: 18,
    rowJitter: 12,
    seed: 42,
    strokeWidth: 0.4,
    fillOpacity: 0.95,
  },
};

/** Factory presets cannot be deleted. */
export const BUILTIN_PRESET_NAMES: readonly string[] = Object.keys(DEFAULT_PRESETS);

export const DEFAULT_PRESET_NAME = 'Regular';
export const DEFAULT_PHRASE = 'НОБЕЛЬФАЙК';

/** Same ladder as CSS / OS/2 usWeightClass: 100, 200, 300… */
export const PRESET_WEIGHT_STEP = 100;

/**
 * Next free style name on the weight ladder: 100, then 200, then 300.
 * Factory names like Regular stay as they are; user styles get the numbers.
 */
export function nextPresetName(existingNames: readonly string[]): string {
  const taken = new Set(existingNames);
  let weight = PRESET_WEIGHT_STEP;
  while (taken.has(String(weight))) {
    weight += PRESET_WEIGHT_STEP;
  }
  return String(weight);
}

/** Specimen used for preview and export when the text field is empty. */
export function resolveSpecimen(text: string): string {
  const trimmed = text.trim();
  return trimmed.length > 0 ? trimmed : DEFAULT_PHRASE;
}

export const DEFAULT_INSPECT_CHAR = 'А';

export function freshPresetLibrary(): Record<string, StyleParams> {
  return Object.fromEntries(
    Object.entries(DEFAULT_PRESETS).map(([name, params]) => [name, { ...params }]),
  );
}

const NUMERIC_KEYS = [
  'rx',
  'ry',
  'strokeWidth',
  'fillOpacity',
  'moduleAngle',
  'moduleFontSymbolsPerModule',
  'stepX',
  'stepY',
  'colScale',
  'rowScale',
  'letterSpacing',
  'slantAngle',
  'jitterX',
  'rowJitter',
  'seed',
] as const satisfies ReadonlyArray<keyof StyleParams>;

const BOOLEAN_KEYS = [
  'moduleFontRandomize',
  'showGuides',
  'showGrid',
] as const satisfies ReadonlyArray<keyof StyleParams>;

const STRING_KEYS = [
  'moduleType',
  'customSvgMarkup',
  'customSvgName',
  'moduleFontSubfamily',
  'moduleFontWeight',
  'moduleFontChars',
  'moduleFontFillOrder',
  'fill',
  'stroke',
  'background',
  'guideColor',
  'gridColor',
] as const satisfies ReadonlyArray<keyof StyleParams>;

/** Merge untrusted partial data onto the reference style, dropping junk. */
export function normalizeParams(raw: unknown): StyleParams {
  const out: StyleParams = { ...REGULAR_PARAMS, kerningPairs: {} };
  if (!raw || typeof raw !== 'object') {
    return out;
  }
  const source = raw as Record<string, unknown>;

  for (const key of NUMERIC_KEYS) {
    const value = source[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
      (out[key] as number) = value;
    }
  }
  for (const key of BOOLEAN_KEYS) {
    if (typeof source[key] === 'boolean') {
      (out[key] as boolean) = source[key] as boolean;
    }
  }
  for (const key of STRING_KEYS) {
    if (typeof source[key] === 'string') {
      (out[key] as string) = source[key] as string;
    }
  }

  if (out.moduleType !== 'oval' && out.moduleType !== 'custom_svg' && out.moduleType !== 'font_symbols') {
    out.moduleType = MODULE_OVAL;
  }
  if (out.moduleFontFillOrder !== 'columns' && out.moduleFontFillOrder !== 'rows') {
    out.moduleFontFillOrder = FILL_ORDER_COLUMNS;
  }

  const kerning = source.kerningPairs;
  if (kerning && typeof kerning === 'object') {
    const pairs: Record<string, number> = {};
    for (const [pair, delta] of Object.entries(kerning as Record<string, unknown>)) {
      if ([...pair].length === 2 && typeof delta === 'number' && Number.isFinite(delta)) {
        pairs[pair] = delta;
      }
    }
    out.kerningPairs = pairs;
  }

  return out;
}

export function presetsToJson(
  presets: PresetLibrary,
  activeName: string | null,
): string {
  const payload: PresetFilePayload = {
    format: PRESET_FILE_FORMAT,
    active: activeName,
    presets: presets as Record<string, StyleParams>,
  };
  return JSON.stringify(payload, null, 2);
}

export interface ParsedPresetFile {
  presets: Record<string, StyleParams>;
  active: string | null;
}

export function presetsFromJson(text: string): ParsedPresetFile {
  const data: unknown = JSON.parse(text);
  if (!data || typeof data !== 'object') {
    throw new Error('JSON должен быть объектом с начертаниями');
  }

  const container = data as Record<string, unknown>;
  const rawPresets =
    container.presets && typeof container.presets === 'object'
      ? (container.presets as Record<string, unknown>)
      : container;

  const presets: Record<string, StyleParams> = {};
  for (const [name, params] of Object.entries(rawPresets)) {
    const label = String(name).trim();
    if (label && params && typeof params === 'object') {
      presets[label] = normalizeParams(params);
    }
  }

  if (Object.keys(presets).length === 0) {
    throw new Error('В файле нет ни одного начертания');
  }

  const active = typeof container.active === 'string' ? container.active : null;
  return { presets, active: active && presets[active] ? active : null };
}
