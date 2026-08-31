import { Tabs } from './Tabs';
import type { TabId } from '../../types/fontTypes';

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
  return (
    <header className="flex shrink-0 flex-col gap-2 border-b border-studio-border bg-studio-bg px-4 pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-[15px] font-semibold tracking-tight text-studio-text">
          CRT Parametric Font Studio
        </h1>
        <p className="font-mono text-[11px] text-studio-faint">
          Активное начертание: <span className="text-studio-muted">{activePreset}</span>
          {' · '}
          {presetCount} в библиотеке
        </p>
      </div>
      <Tabs active={activeTab} onChange={onTabChange} />
    </header>
  );
}
