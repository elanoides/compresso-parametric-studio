import { useCallback } from 'react';

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  /** Decimal places in the value readout; defaults to the step's precision. */
  precision?: number;
  suffix?: string;
}

function precisionFor(step: number): number {
  if (Number.isInteger(step)) {
    return 0;
  }
  const decimals = String(step).split('.')[1];
  return decimals ? decimals.length : 1;
}

/**
 * Range input wired to React's `onChange`, which fires on every `input` event —
 * the preview follows the thumb without waiting for mouse release.
 */
export function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
  precision,
  suffix = '',
}: SliderProps) {
  const digits = precision ?? precisionFor(step);

  const handleChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      onChange(Number.parseFloat(event.target.value));
    },
    [onChange],
  );

  return (
    <label className="block select-none">
      <span className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-[11px] tracking-wide text-studio-muted">{label}</span>
        <span className="font-mono text-[11px] tabular-nums text-studio-text">
          {value.toFixed(digits)}
          {suffix}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={handleChange}
        aria-label={label}
      />
    </label>
  );
}
