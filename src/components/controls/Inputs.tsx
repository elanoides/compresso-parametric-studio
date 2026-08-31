import type { ReactNode } from 'react';

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
