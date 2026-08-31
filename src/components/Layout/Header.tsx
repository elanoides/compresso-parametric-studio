import { useMemo } from 'react';

import { SvgCanvas } from '../SvgCanvas';
import { Tabs } from './Tabs';
import { REGULAR_PARAMS } from '../../data/presets';
import { renderTextSvg } from '../../engine/geometry';
import type { RenderContext, TabId } from '../../types/fontTypes';

const TITLE = 'COMPRESSO PARAMETRIC FONT STUDIO';

const TITLE_CONTEXT: RenderContext = {
  params: REGULAR_PARAMS,
  fontPaths: {},
  fontAlphabet: '',
};

interface HeaderProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  activePreset: string;
  presetCount: number;
}

export function Header({
  activeTab,
  onTabChange,
  activePreset,
  presetCount,
}: HeaderProps) {
  const titleSvg = useMemo(
    () =>
      renderTextSvg(TITLE, TITLE_CONTEXT, 1, {
        paintBackground: false,
        contain: true,
      }),
    [],
  );

  return (
    <header className="flex shrink-0 flex-col gap-2 border-b border-studio-border bg-studio-bg px-4 pt-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="min-w-0 flex-1">
          <span className="sr-only">Compresso Parametric Font Studio</span>
          <div className="h-16 max-w-[1100px]">
            <SvgCanvas svg={titleSvg} fluid />
          </div>
        </h1>
        <p className="shrink-0 font-mono text-[11px] text-studio-faint">
          Активное начертание: <span className="text-studio-muted">{activePreset}</span>
          {' · '}
          {presetCount} в библиотеке
        </p>
      </div>
      <Tabs active={activeTab} onChange={onTabChange} />
    </header>
  );
}
