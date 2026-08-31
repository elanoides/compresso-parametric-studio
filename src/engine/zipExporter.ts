/**
 * Family pack builder: one ZIP holding every style as SVG alphabet, specimen,
 * settings JSON and a ready-to-install OpenType binary.
 */

import JSZip from 'jszip';

import type { PresetLibrary, RenderContext, StyleParams } from '../types/fontTypes';
import { GLYPH_CHARS } from './glyphs';
import { glyphFileName } from './download';
import { renderGlyphSvg, renderTextSvg } from './geometry';
import { styleSlug } from './fontNaming';
import { buildFontBinary } from './opentypeExporter';
import { resolveFontPathsFor } from './renderContext';
import { resolveSpecimen } from '../data/presets';

export const FAMILY_PACK_FILENAME = 'Compresso_Parametric_Family_Pack.zip';

export interface FamilyPackOptions {
  family: string;
  specimen: string;
  /** Called after each style so the UI can show progress. */
  onProgress?: (done: number, total: number, styleName: string) => void;
}

/**
 * Build the family archive. Font outlines are resolved per style, so a style
 * using font-symbol modules pulls in exactly the face it needs.
 */
export async function buildFamilyPack(
  presets: PresetLibrary,
  options: FamilyPackOptions,
): Promise<Blob> {
  const zip = new JSZip();
  const entries = Object.entries(presets);
  const total = entries.length;

  zip.file(
    'presets.json',
    JSON.stringify(
      { format: 'crt-font-studio-presets-v3', active: null, presets },
      null,
      2,
    ),
  );

  let done = 0;
  for (const [styleName, params] of entries) {
    const folder = styleSlug(styleName);
    const ctx = await buildStyleContext(params);

    const glyphFolder = `${folder}/svg`;
    for (const ch of GLYPH_CHARS) {
      zip.file(`${glyphFolder}/${glyphFileName(ch)}.svg`, renderGlyphSvg(ch, ctx));
    }

    zip.file(`${folder}/specimen.svg`, renderTextSvg(resolveSpecimen(options.specimen), ctx, 1));
    zip.file(`${folder}/params.json`, JSON.stringify(params, null, 2));

    try {
      const font = buildFontBinary(ctx, { family: options.family, styleName });
      zip.file(`${folder}/${font.filename}`, font.binary);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      zip.file(`${folder}/FONT_ERROR.txt`, `Не удалось собрать шрифт: ${message}\n`);
    }

    done += 1;
    options.onProgress?.(done, total, styleName);
    // Yield to the event loop so the progress indicator can paint.
    await new Promise((resolve) => setTimeout(resolve, 0));
  }

  return zip.generateAsync({ type: 'blob', compression: 'DEFLATE' });
}

async function buildStyleContext(params: StyleParams): Promise<RenderContext> {
  const resolved = await resolveFontPathsFor(params);
  return { params, fontPaths: resolved.paths, fontAlphabet: resolved.alphabet };
}
