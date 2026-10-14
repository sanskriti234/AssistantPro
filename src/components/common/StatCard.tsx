export function StatCard({ label, value, hint, tone = 'default' }: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: 'default' | 'accent' | 'verified' | 'blocked' | 'warning';
}) {
  const toneClass = {
    default: 'text-text',
    accent: 'text-accent',
    verified: 'text-verified',
    blocked: 'text-blocked',
    warning: 'text-warning',
  }[tone];

  return (
    <div className="bg-surface border border-border-soft rounded-xl px-5 py-4 rise-in">
      <p className="text-xs uppercase tracking-wider text-text-faint">{label}</p>
      <p className={`font-mono text-2xl font-semibold mt-2 ${toneClass}`}>{value}</p>
      {hint && <p className="text-xs text-text-dim mt-1">{hint}</p>}
    </div>
  );
}
