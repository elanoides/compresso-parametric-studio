import { useCallback, useMemo, useState } from 'react';

import { Button } from '../controls/Button';
import { Checkbox } from '../controls/Inputs';
import { SvgCanvas } from '../SvgCanvas';
import { downloadSvg, glyphFileName } from '../../engine/download';
import { renderGlyphSvg } from '../../engine/geometry';
import {
  BASELINE,
  BODY_BOTTOM,
  BODY_TOP,
  CAP_HEIGHT,
  GLYPH_CHARS,
  ROWS_TOTAL,
  getGlyph,
  glyphWidth,
} from '../../engine/glyphs';
import { styleSlug } from '../../engine/fontNaming';
import type { RenderContext } from '../../types/fontTypes';

interface GlyphInspectorProps {
  context: RenderContext;
  activePreset: string;
  char: string;
  onCharChange: (char: string) => void;
}

export function GlyphInspector({
  context,
  activePreset,
  char,
  onCharChange,
}: GlyphInspectorProps) {
  const [showGrid, setShowGrid] = useState(true);
  const [showGuides, setShowGuides] = useState(true);

  const inspectorContext = useMemo<RenderContext>(
    () => ({ ...context, params: { ...context.params, showGrid, showGuides } }),
    [context, showGrid, showGuides],
  );

  const svg = useMemo(() => renderGlyphSvg(char, inspectorContext), [char, inspectorContext]);

  const modules = useMemo(
    () => getGlyph(char, context.params.colScale, context.params.rowScale),
    [char, context.params.colScale, context.params.rowScale],
  );

  const download = useCallback(() => {
    downloadSvg(svg, `${styleSlug(activePreset)}-${glyphFileName(char)}.svg`);
  }, [activePreset, char, svg]);

  const columns = glyphWidth(char) * Math.max(1, context.params.colScale);

  return (
    <div className="flex h-full min-h-0 gap-4">
      <div className="flex w-[190px] shrink-0 flex-col gap-2">
        <span className="text-[11px] tracking-wide text-studio-muted">Символ</span>
        <div className="grid grid-cols-6 gap-1 overflow-y-auto rounded-lg border border-studio-border bg-studio-panel p-2">
          {GLYPH_CHARS.map((candidate) => {
            const selected = candidate === char;
            return (
              <button
                key={candidate}
                type="button"
                onClick={() => onCharChange(candidate)}
                aria-pressed={selected}
                className={
                  'aspect-square rounded font-mono text-[12px] transition-colors ' +
                  (selected
                    ? 'bg-white font-bold text-black'
                    : 'text-studio-muted hover:bg-studio-raised hover:text-studio-text')
                }
              >
                {candidate}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
          <Checkbox label="Сетка координат" checked={showGrid} onChange={setShowGrid} />
          <Checkbox label="Метрики" checked={showGuides} onChange={setShowGuides} />
        </div>

        <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto rounded-lg border border-studio-border bg-studio-panel p-4">
          <SvgCanvas svg={svg} />
        </div>

        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-[11px] text-studio-muted sm:grid-cols-4">
          <Metric label="Модулей" value={String(modules.length)} />
          <Metric label="Колонок" value={String(columns)} />
          <Metric label="Строк в сетке" value={String(ROWS_TOTAL)} />
          <Metric label="Cap-Height" value={`${CAP_HEIGHT} строк`} />
          <Metric label="Тело знака" value={`${BODY_TOP}…${BODY_BOTTOM}`} />
          <Metric label="Baseline" value={`строка ${BASELINE}`} />
          <Metric label="Акценты" value="строки 0…3" />
          <Metric label="Выносные" value="строки 24…27" />
        </dl>

        <div>
          <Button onClick={download}>Скачать SVG знака</Button>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 border-b border-studio-border pb-0.5">
      <dt>{label}</dt>
      <dd className="text-studio-text">{value}</dd>
    </div>
  );
}
