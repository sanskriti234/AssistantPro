type Tone = 'verified' | 'blocked' | 'warning' | 'neutral' | 'accent';

const toneStyles: Record<Tone, string> = {
  verified: 'bg-verified/10 text-verified border-verified/30',
  blocked: 'bg-blocked/10 text-blocked border-blocked/30',
  warning: 'bg-warning/10 text-warning border-warning/30',
  neutral: 'bg-surface-3 text-text-dim border-border-soft',
  accent: 'bg-accent/10 text-accent border-accent/30',
};

export function StatusPill({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${toneStyles[tone]}`}>
      {children}
    </span>
  );
}
