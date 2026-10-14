import type { RecognitionResult } from '../../types';
import { EmptyState } from '../common/EmptyState';

export function RecentVerifiedList({ items }: { items: RecognitionResult[] }) {
  if (items.length === 0) {
    return (
      <div className="bg-surface border border-border-soft rounded-xl">
        <EmptyState title="No one verified yet" description="Recognized students will appear here as they're marked present." />
      </div>
    );
  }

  return (
    <div className="bg-surface border border-border-soft rounded-xl divide-y divide-border-soft">
      {items.map((r, i) => (
        <div key={i} className="flex items-center justify-between px-4 py-3">
          <div>
            <p className="text-sm text-text">{r.studentName}</p>
            <p className="font-mono text-[11px] text-text-dim">{r.rollNumber}</p>
          </div>
          <span className="font-mono text-xs text-verified">{r.recognitionScore}%</span>
        </div>
      ))}
    </div>
  );
}
