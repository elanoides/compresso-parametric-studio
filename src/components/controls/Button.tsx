import type { MouseEvent, ReactNode } from 'react';

export type ButtonVariant = 'default' | 'primary' | 'inverted' | 'danger' | 'ghost';

interface ButtonProps {
  children: ReactNode;
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void;
  variant?: ButtonVariant;
  disabled?: boolean;
  title?: string;
  fullWidth?: boolean;
  compact?: boolean;
  type?: 'button' | 'submit';
}

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  default:
    'border-studio-border bg-studio-surface text-studio-text hover:border-white disabled:hover:border-studio-border',
  primary: 'border-white bg-studio-raised text-white font-semibold hover:bg-[#2a2a2a]',
  inverted: 'border-black bg-black text-white font-semibold hover:bg-[#1a1a1a]',
  danger: 'border-[#ff5a52] bg-[#ff5a52] text-black font-semibold hover:bg-[#ff746d]',
  ghost:
    'border-transparent bg-transparent text-studio-muted hover:border-studio-border hover:text-studio-text',
};

export function Button({
  children,
  onClick,
  variant = 'default',
  disabled = false,
  title,
  fullWidth = false,
  compact = false,
  type = 'button',
}: ButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
      className={
        'inline-flex items-center justify-center rounded border text-[12px] whitespace-nowrap transition-colors ' +
        'disabled:cursor-not-allowed disabled:opacity-40 ' +
        (compact ? 'px-2 py-1.5 ' : 'px-3 py-2 ') +
        (fullWidth ? 'w-full ' : '') +
        VARIANT_CLASS[variant]
      }
    >
      {children}
    </button>
  );
}
