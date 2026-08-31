/**
 * Catalog lookups over the local SB Sans / SB Serif faces in `public/fonts/`.
 *
 * Kept free of `opentype.js` so the sidebar can list families without pulling
 * the font parser into the initial bundle.
 */

import { MODULE_FONT_CATALOG } from './moduleFonts';

export { MODULE_FONT_CATALOG };

export const MODULE_FONT_SUBFAMILIES: readonly string[] = Object.keys(MODULE_FONT_CATALOG);

export function weightsForSubfamily(subfamily: string): readonly string[] {
  const bucket = MODULE_FONT_CATALOG[subfamily];
  return bucket ? Object.keys(bucket) : [];
}

/** Resolve a subfamily + weight pair to a filename in `public/fonts/`. */
export function resolveFontFile(subfamily: string, weight: string): string {
  const bucket = MODULE_FONT_CATALOG[subfamily];
  if (!bucket) {
    return '';
  }
  if (bucket[weight]) {
    return bucket[weight];
  }
  return Object.values(bucket)[0] ?? '';
}
