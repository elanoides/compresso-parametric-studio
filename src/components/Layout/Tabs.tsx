import type { TabId } from '../../types/fontTypes';

export const TAB_LABELS: ReadonlyArray<{ id: TabId; label: string }> = [
  { id: 'word', label: 'Наборщик текста' },
  { id: 'glyph', label: 'Инспектор глифа' },
  { id: 'styles', label: 'Начертания' },
];

interface TabsProps {
  active: TabId;
  onChange: (tab: TabId) => void;
}

export function Tabs({ active, onChange }: TabsProps) {
  return (
    <nav className="flex gap-1" role="tablist" aria-label="Разделы студии">
      {TAB_LABELS.map((tab) => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab.id)}
            className={
              'rounded-t border-b-2 px-3.5 py-2 text-[12px] transition-colors ' +
              (selected
                ? 'border-white font-semibold text-white'
                : 'border-transparent text-studio-muted hover:text-studio-text')
            }
          >
            {tab.label}
          </button>
        );
      })}
    </nav>
  );
}
