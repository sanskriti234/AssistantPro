import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';

const variants: Record<Variant, string> = {
  primary: 'bg-accent text-base font-semibold hover:brightness-110',
  secondary: 'bg-surface-3 text-text border border-border hover:bg-surface-2',
  danger: 'bg-blocked/10 text-blocked border border-blocked/40 hover:bg-blocked/20',
  ghost: 'text-text-dim hover:text-text hover:bg-surface-2',
};

export function Button({ variant = 'primary', className = '', disabled, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      disabled={disabled}
      className={`px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${variants[variant]} ${className}`}
      {...rest}
    />
  );
}
