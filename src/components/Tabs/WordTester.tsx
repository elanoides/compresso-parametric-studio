import { useCallback, useDeferredValue, useMemo, useState } from 'react';

import { Button } from '../controls/Button';
import { Slider } from '../controls/Slider';
import { SvgCanvas } from '../SvgCanvas';
import { saveAs } from 'file-saver';
import { downloadFont, downloadSvg } from '../../engine/download';
import { FONT_FAMILY, styleSlug } from '../../engine/fontNaming';
import { renderTextSvg } from '../../engine/geometry';
import type { RenderContext, StyleParams } from '../../types/fontTypes';

interface WordTesterProps {
  context: RenderContext;
  presets: Record<string, StyleParams>;
  activePreset: string;
  text: string;
  onTextChange: (text: string) => void;
  previewScale: number;
  onPreviewScaleChange: (scale: number) => void;
}

export function WordTester({
  context,
  presets,
  activePreset,
  text,
  onTextChange,
  previewScale,
  onPreviewScaleChange,
}: WordTesterProps) {
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Deferring the heavy render keeps slider input at 60 FPS: React paints the
  // thumb immediately and recomputes the SVG in an interruptible pass.
  const deferredContext = useDeferredValue(context);
  const deferredText = useDeferredValue(text);
  const deferredScale = useDeferredValue(previewScale);

  const svg = useMemo(
    () => renderTextSvg(deferredText, deferredContext, deferredScale),
    [deferredText, deferredContext, deferredScale],
  );

  const exportSvg = useCallback(() => {
    const full = renderTextSvg(text, context, 1);
    downloadSvg(full, `${styleSlug(activePreset)}-specimen.svg`);
    setStatus('SVG сохранён');
  }, [activePreset, context, text]);

  // The font tooling is a 300 kB chunk; it loads only when an export is asked for.
  const exportFont = useCallback(async () => {
    setBusy(true);
    setStatus('Сборка шрифта…');
    try {
      const { buildFontBinary } = await import('../../engine/opentypeExporter');
      const font = buildFontBinary(context, {
        family: FONT_FAMILY,
        styleName: activePreset,
      });
      downloadFont(font.binary, font.filename);
      setStatus(
        `Шрифт собран: ${font.filename}` +
          (font.kernPairCount > 0 ? ` · кернинг ${font.kernPairCount} пар` : ''),
      );
    } catch (error) {
      setStatus(
        `Ошибка сборки шрифта: ${error instanceof Error ? error.message : String(error)}`,
      );
    } finally {
      setBusy(false);
    }
  }, [activePreset, context]);

  const exportFamily = useCallback(async () => {
    setBusy(true);
    setStatus('Сборка архива…');
    try {
      const { FAMILY_PACK_FILENAME, buildFamilyPack } = await import(
        '../../engine/zipExporter'
      );
      const blob = await buildFamilyPack(presets, {
        family: FONT_FAMILY,
        specimen: text || 'НОБЕЛЬФАЙК',
        onProgress: (done, total, styleName) => {
          setStatus(`Начертание ${done} из ${total}: ${styleName}`);
        },
      });
      saveAs(blob, FAMILY_PACK_FILENAME);
      setStatus(`Архив собран: ${FAMILY_PACK_FILENAME}`);
    } catch (error) {
      setStatus(
        `Ошибка сборки архива: ${error instanceof Error ? error.message : String(error)}`,
      );
    } finally {
      setBusy(false);
    }
  }, [presets, text]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex flex-wrap items-end gap-4">
        <label className="min-w-[240px] flex-1">
          <span className="mb-1 block text-[11px] tracking-wide text-studio-muted">
            Текст (All-Caps)
          </span>
          <input
            type="text"
            value={text}
            onChange={(event) => onTextChange(event.target.value.toUpperCase())}
            placeholder="НОБЕЛЬФАЙК"
            className="w-full rounded border border-studio-border bg-studio-panel px-3 py-2 font-mono text-[15px] tracking-wide text-studio-text outline-none focus:border-studio-border-strong"
            aria-label="Текст для набора"
          />
        </label>
        <div className="w-[220px]">
          <Slider
            label="Размер шрифта"
            value={previewScale}
            min={0.1}
            max={1.5}
            step={0.01}
            onChange={onPreviewScaleChange}
          />
        </div>
      </div>

      <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto rounded-lg border border-studio-border bg-studio-panel p-4">
        <SvgCanvas svg={svg} />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={exportSvg} disabled={busy}>
          Экспорт SVG
        </Button>
        <Button onClick={() => void exportFont()} disabled={busy} variant="primary">
          Скачать шрифт (OTF)
        </Button>
        <Button onClick={() => void exportFamily()} disabled={busy}>
          Экспорт семейства (ZIP)
        </Button>
        {status ? (
          <span className="font-mono text-[11px] text-studio-muted">{status}</span>
        ) : null}
      </div>
    </div>
  );
}
