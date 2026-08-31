/** Character pools used by the font-symbol module type. */

/**
 * Default pool when «Строка символов» is empty: readable letters, digits and
 * punctuation only — no technical or invisible glyphs.
 */
export const READABLE_CHAR_POOL =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZ' +
  'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ' +
  '0123456789' +
  '.,:;!?/+-=';

/**
 * Circle- or dot-like at module scale — indistinguishable from a plain oval,
 * so they are never used as font modules.
 */
export const RANDOM_EXCLUDED_CHARS = new Set('O0QОo.°,;·•●◦∙');
