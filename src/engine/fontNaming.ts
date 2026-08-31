/**
 * Font naming and OS/2 style metrics.
 *
 * Separate from the exporter so filenames and slugs are available without
 * loading `opentype.js`.
 */

export const FONT_FAMILY = 'Compresso Parametric';
export const DEFAULT_STYLE_NAME = 'Regular';

const WEIGHT_BY_TOKEN: ReadonlyArray<readonly [string, number]> = [
  ['thin', 100],
  ['extralight', 200],
  ['ultralight', 200],
  ['light', 300],
  ['book', 400],
  ['regular', 400],
  ['normal', 400],
  ['medium', 500],
  ['semibold', 600],
  ['demibold', 600],
  ['bold', 700],
  ['extrabold', 800],
  ['ultrabold', 800],
  ['black', 900],
  ['heavy', 900],
];

const WIDTH_BY_TOKEN: ReadonlyArray<readonly [string, number]> = [
  ['ultracondensed', 1],
  ['extracondensed', 2],
  ['condensed', 3],
  ['narrow', 3],
  ['semicondensed', 4],
  ['normal', 5],
  ['regular', 5],
  ['semiexpanded', 6],
  ['expanded', 7],
  ['wide', 7],
  ['extraexpanded', 8],
  ['ultraexpanded', 9],
];

const PUNCTUATION_NAMES: Readonly<Record<string, string>> = {
  '.': 'period',
  ',': 'comma',
  ':': 'colon',
  ';': 'semicolon',
  '!': 'exclam',
  '?': 'question',
  '/': 'slash',
  '+': 'plus',
  '-': 'hyphen',
  '=': 'equal',
  ' ': 'space',
};

const DIGIT_NAMES = [
  'zero',
  'one',
  'two',
  'three',
  'four',
  'five',
  'six',
  'seven',
  'eight',
  'nine',
];

/** PostScript-safe glyph name (CFF charsets reject names starting with a digit). */
export function glyphName(ch: string): string {
  const punctuation = PUNCTUATION_NAMES[ch];
  if (punctuation) {
    return punctuation;
  }
  if (ch >= '0' && ch <= '9') {
    return DIGIT_NAMES[ch.charCodeAt(0) - 48];
  }
  if (ch >= 'A' && ch <= 'Z') {
    return ch;
  }
  return `uni${ch.codePointAt(0)!.toString(16).toUpperCase().padStart(4, '0')}`;
}

export interface StyleMetrics {
  weightClass: number;
  widthClass: number;
  fsSelection: number;
  italic: boolean;
}

/** Derive OS/2 metrics from a free-form style name. */
export function resolveStyleMetrics(style: string): StyleMetrics {
  const tokens = new Set(
    style
      .replace(/[^0-9a-zA-Z]+/g, ' ')
      .toLowerCase()
      .split(' ')
      .filter(Boolean),
  );

  let weightClass = 400;
  const numericName = Number(style.trim());
  if (
    /^\d+$/.test(style.trim()) &&
    Number.isInteger(numericName) &&
    numericName >= 1
  ) {
    weightClass = Math.min(1000, numericName);
  } else {
    for (const [token, value] of WEIGHT_BY_TOKEN) {
      if (tokens.has(token)) {
        weightClass = value;
        break;
      }
    }
  }

  let widthClass = 5;
  for (const [token, value] of WIDTH_BY_TOKEN) {
    if (tokens.has(token)) {
      widthClass = value;
      break;
    }
  }

  const italic = tokens.has('italic') || tokens.has('oblique');
  let fsSelection = 0;
  if (italic) {
    fsSelection |= 0x01;
  }
  if (weightClass >= 700) {
    fsSelection |= 0x20;
  } else if (!italic) {
    fsSelection |= 0x40;
  }

  return { weightClass, widthClass, fsSelection, italic };
}

/** Filesystem-safe token for download filenames and ZIP folders. */
export function styleSlug(style: string): string {
  const slug = style
    .trim()
    .replace(/[^0-9A-Za-zА-Яа-яЁё]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || 'Style';
}

/**
 * Non-RIBBI styles get a unique Windows family so they do not collapse onto
 * Regular in the system font menu.
 */
export function windowsFamilyName(family: string, styleName: string): string {
  const key = styleName.replace(/[^0-9a-zA-Z]+/g, '').toLowerCase();
  const ribbi = new Set(['regular', 'bold', 'italic', 'bolditalic']);
  return ribbi.has(key) ? family : `${family} ${styleName}`;
}
