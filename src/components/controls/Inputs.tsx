import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';

const FIELD_CLASS =
  'w-full rounded border border-studio-border bg-studio-panel px-2 py-1.5 text-[12px] ' +
  'text-studio-text outline-none transition-colors focus:border-studio-border-strong';

export function FieldLabel({ children }: { children: ReactNode }) {
  return (
    <span className="mb-1 block text-[11px] tracking-wide text-studio-muted">{children}</span>
  );
}

interface TextFieldProps {
  label?: string;
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
  onKeyDown?: (event: React.KeyboardEvent<HTMLInputElement>) => void;
  maxLength?: number;
  className?: string;
}

export function TextField({
  label,
  value,
  placeholder,
  onChange,
  onKeyDown,
  maxLength,
  className = '',
}: TextFieldProps) {
  return (
    <label className="block">
      {label ? <FieldLabel>{label}</FieldLabel> : null}
      <input
        type="text"
        className={`${FIELD_CLASS} ${className}`}
        value={value}
        placeholder={placeholder}
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKeyDown}
        aria-label={label ?? placeholder ?? 'Текстовое поле'}
      />
    </label>
  );
}

interface SelectProps {
  label?: string;
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
  disabled?: boolean;
}

interface ComboboxProps {
  label?: string;
  value: string;
  options: readonly string[];
  onSelect: (value: string) => void;
  /** Create a new entry from the typed query. Return an error string, or null on success. */
  onCreate?: (name: string) => string | null;
  placeholder?: string;
}

/**
 * Editable combobox: type to filter the list, pick an existing option, or
 * confirm a new name with Enter / the create row.
 *
 * While the field still holds the committed value, the full list is shown so
 * opening the control is a directory, not a filter of the current name.
 */
export function Combobox({
  label,
  value,
  options,
  onSelect,
  onCreate,
  placeholder = 'Найти или ввести имя',
}: ComboboxProps) {
  const listId = useId();
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [highlight, setHighlight] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setQuery(value);
      setError(null);
    }
  }, [value, open]);

  const trimmed = query.trim();
  const browsing = trimmed === '' || trimmed === value;
  const filtered = useMemo(() => {
    if (browsing) {
      return [...options];
    }
    const needle = trimmed.toLowerCase();
    return options.filter((name) => name.toLowerCase().includes(needle));
  }, [browsing, options, trimmed]);

  const exactMatch = options.some((name) => name === trimmed);
  const canCreate = Boolean(onCreate) && trimmed.length > 0 && !exactMatch;
  const itemCount = filtered.length + (canCreate ? 1 : 0);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const onPointer = (event: PointerEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('pointerdown', onPointer);
    return () => document.removeEventListener('pointerdown', onPointer);
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    wrapRef.current
      ?.querySelector('[data-combo-active="true"]')
      ?.scrollIntoView({ block: 'nearest' });
  }, [highlight, open]);

  const reveal = () => {
    const index = options.indexOf(value);
    setHighlight(index >= 0 ? index : 0);
    setOpen(true);
  };

  const close = () => {
    setOpen(false);
    setQuery(value);
    setError(null);
  };

  const pick = (name: string) => {
    onSelect(name);
    setQuery(name);
    setError(null);
    setOpen(false);
  };

  const create = () => {
    if (!onCreate || !canCreate) {
      return;
    }
    const result = onCreate(trimmed);
    if (result) {
      setError(result);
      return;
    }
    setQuery(trimmed);
    setError(null);
    setOpen(false);
  };

  const activateHighlighted = () => {
    if (highlight < filtered.length) {
      const name = filtered[highlight];
      if (name) {
        pick(name);
      }
      return;
    }
    create();
  };

  return (
    <div ref={wrapRef} className="relative">
      {label ? <FieldLabel>{label}</FieldLabel> : null}
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-label={label ?? placeholder}
          value={query}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          className={`${FIELD_CLASS} pr-7`}
          onChange={(event) => {
            setQuery(event.target.value);
            setHighlight(0);
            setError(null);
            setOpen(true);
          }}
          onFocus={(event) => {
            reveal();
            event.currentTarget.select();
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault();
              setOpen(true);
              setHighlight((index) => Math.min(index + 1, Math.max(itemCount - 1, 0)));
            } else if (event.key === 'ArrowUp') {
              event.preventDefault();
              setHighlight((index) => Math.max(index - 1, 0));
            } else if (event.key === 'Enter') {
              event.preventDefault();
              if (open && itemCount > 0) {
                activateHighlighted();
              } else if (exactMatch) {
                pick(trimmed);
              } else {
                create();
              }
            } else if (event.key === 'Escape') {
              event.preventDefault();
              close();
              inputRef.current?.blur();
            }
          }}
        />
        <button
          type="button"
          tabIndex={-1}
          aria-label="Показать список начертаний"
          className="absolute top-1/2 right-1.5 -translate-y-1/2 text-studio-muted"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => {
            if (open) {
              close();
              return;
            }
            reveal();
            inputRef.current?.focus();
            inputRef.current?.select();
          }}
        >
          <ChevronDown
            size={14}
            className={`transition-transform ${open ? 'rotate-180' : ''}`}
            aria-hidden
          />
        </button>
      </div>
      {open ? (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-52 w-full overflow-y-auto rounded border border-studio-border-strong bg-studio-panel py-1 shadow-lg"
        >
          {filtered.map((name, index) => {
            const active = index === highlight;
            return (
              <li key={name} role="option" aria-selected={active}>
                <button
                  type="button"
                  data-combo-active={active ? 'true' : undefined}
                  className={
                    'flex w-full px-2 py-1.5 text-left text-[12px] ' +
                    (name === value ? 'font-semibold text-white ' : 'text-studio-text ') +
                    (active ? 'bg-studio-raised' : 'hover:bg-studio-raised')
                  }
                  onMouseEnter={() => setHighlight(index)}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => pick(name)}
                >
                  {name}
                </button>
              </li>
            );
          })}
          {filtered.length === 0 && !canCreate ? (
            <li className="px-2 py-1.5 text-[11px] text-studio-faint">Ничего не найдено</li>
          ) : null}
          {canCreate ? (
            <li role="option" aria-selected={highlight === filtered.length}>
              <button
                type="button"
                data-combo-active={highlight === filtered.length ? 'true' : undefined}
                className={
                  'flex w-full px-2 py-1.5 text-left text-[12px] text-studio-text ' +
                  (highlight === filtered.length ? 'bg-studio-raised' : 'hover:bg-studio-raised')
                }
                onMouseEnter={() => setHighlight(filtered.length)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={create}
              >
                Создать «{trimmed}»
              </button>
            </li>
          ) : null}
        </ul>
      ) : null}
      {error ? <p className="mt-1 text-[10px] text-[#ff5a52]">{error}</p> : null}
    </div>
  );
}

export function Select({ label, value, options, onChange, disabled }: SelectProps) {
  return (
    <label className="block">
      {label ? <FieldLabel>{label}</FieldLabel> : null}
      <select
        className={`${FIELD_CLASS} disabled:opacity-50`}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        aria-label={label ?? 'Выбор'}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

interface RadioGroupProps<T extends string> {
  label?: string;
  value: T;
  options: ReadonlyArray<{ value: T; label: string }>;
  onChange: (value: T) => void;
  columns?: number;
}

export function RadioGroup<T extends string>({
  label,
  value,
  options,
  onChange,
  columns = 1,
}: RadioGroupProps<T>) {
  return (
    <div>
      {label ? <FieldLabel>{label}</FieldLabel> : null}
      <div
        className="grid gap-1"
        style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
        role="radiogroup"
        aria-label={label ?? 'Выбор варианта'}
      >
        {options.map((option) => {
          const active = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(option.value)}
              className={
                'rounded border px-2 py-1.5 text-[11px] transition-colors ' +
                (active
                  ? 'border-white bg-studio-raised font-semibold text-white'
                  : 'border-studio-border bg-studio-panel text-studio-muted hover:border-studio-border-strong hover:text-studio-text')
              }
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

interface CheckboxProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

export function Checkbox({ label, checked, onChange }: CheckboxProps) {
  return (
    <label className="flex cursor-pointer items-center gap-2 py-0.5 select-none">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-3.5 w-3.5 accent-white"
      />
      <span className="text-[12px] text-studio-text">{label}</span>
    </label>
  );
}

interface ColorFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

export function ColorField({ label, value, onChange }: ColorFieldProps) {
  return (
    <label className="flex items-center justify-between gap-2 py-0.5">
      <span className="text-[11px] tracking-wide text-studio-muted">{label}</span>
      <span className="flex items-center gap-2">
        <span className="font-mono text-[10px] tabular-nums text-studio-faint">
          {value.toUpperCase()}
        </span>
        <input
          type="color"
          value={value}
          onChange={(event) => onChange(event.target.value.toUpperCase())}
          className="h-6 w-9"
          aria-label={label}
        />
      </span>
    </label>
  );
}
