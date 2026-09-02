import { useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';

interface AccordionProps {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}

export function Accordion({ title, children, defaultOpen = false }: AccordionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="shrink-0 overflow-hidden rounded-lg border border-studio-border bg-studio-surface">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left transition-colors hover:bg-studio-raised"
      >
        <span className="text-[12px] font-semibold tracking-wide text-studio-text uppercase">
          {title}
        </span>
        <ChevronDown
          size={14}
          className={`shrink-0 text-studio-muted transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden
        />
      </button>
      {open ? (
        <div className="flex flex-col gap-3 border-t border-studio-border px-3 py-3">
          {children}
        </div>
      ) : null}
    </section>
  );
}
