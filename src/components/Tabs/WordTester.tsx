import { useCallback, useDeferredValue, useMemo, useState } from 'react';

import { Button } from '../controls/Button';
import { Slider } from '../controls/Slider';
import { SvgCanvas } from '../SvgCanvas';
import { resolveSpecimen } from '../../data/presets';
import { downloadFont } from '../../engine/download';
import { FONT_FAMILY } from '../../engine/fontNaming';
import { renderTextSvg } from '../../engine/geometry';
import type { RenderContext } from '../../types/fontTypes';

interface WordTesterProps {
  context: RenderContext;
  activePreset: string;
  text: string;
  onTextChange: (text: string) => void;
  previewScale: number;
  onPreviewScaleChange: (scale: number) => void;
}

export function WordTester({
  context,
  activePreset,
  text,
  onTextChange,
  previewScale,
  onPreviewScaleChange,
}: WordTesterProps) {
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const deferredContext = useDeferredValue(context);
  const deferredText = useDeferredValue(text);
  const deferredScale = useDeferredValue(previewScale);
  const previewText = resolveSpecimen(deferredText);

  const svg = useMemo(
    () =>
      renderTextSvg(previewText, deferredContext, deferredScale, {
        paintBackground: false,
      }),
    [previewText, deferredContext, deferredScale],
  );

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

      <div
        className="flex min-h-0 flex-1 items-center justify-center overflow-auto rounded-lg border border-studio-border"
        style={{ backgroundColor: context.params.background }}
      >
        <SvgCanvas svg={svg} className="p-4" />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => void exportFont()} disabled={busy} variant="primary">
          Скачать шрифт (OTF)
        </Button>
        {status ? (
          <span className="font-mono text-[11px] text-studio-muted">{status}</span>
        ) : null}
      </div>
    </div>
  );
}
