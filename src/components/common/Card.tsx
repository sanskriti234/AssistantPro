import type { HTMLAttributes, ReactNode } from 'react';

export function Card({ children, className = '', ...rest }: { children: ReactNode } & HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`bg-surface border border-border-soft rounded-xl ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between px-5 pt-5">
      <div>
        <h3 className="font-display text-sm font-semibold tracking-wide text-text">{title}</h3>
        {subtitle && <p className="text-xs text-text-dim mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
