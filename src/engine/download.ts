/** Browser download helpers — everything is produced client-side. */

import { saveAs } from 'file-saver';

export function downloadSvg(svg: string, filename: string): void {
  saveAs(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }), filename);
}

export function downloadJson(json: string, filename: string): void {
  saveAs(new Blob([json], { type: 'application/json;charset=utf-8' }), filename);
}

export function downloadBinary(
  data: ArrayBuffer,
  filename: string,
  mime = 'application/octet-stream',
): void {
  saveAs(new Blob([data], { type: mime }), filename);
}

export function downloadFont(binary: ArrayBuffer, filename: string): void {
  downloadBinary(binary, filename, 'font/otf');
}

/** Read a user-selected file as UTF-8 text. */
export function readTextFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ''));
    reader.onerror = () => reject(new Error(`Не удалось прочитать файл ${file.name}`));
    reader.readAsText(file, 'utf-8');
  });
}

/** Filename-safe token for a glyph character. */
export function glyphFileName(ch: string): string {
  return /^[0-9A-Za-z]$/.test(ch)
    ? ch
    : `u${ch.codePointAt(0)!.toString(16).toUpperCase().padStart(4, '0')}`;
}
