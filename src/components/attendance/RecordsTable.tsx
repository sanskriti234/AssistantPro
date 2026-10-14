import type { AttendanceRecord } from '../../types';
import { StatusPill } from '../common/StatusPill';
import { EmptyState } from '../common/EmptyState';

export function RecordsTable({ records }: { records: AttendanceRecord[] }) {
  if (records.length === 0) {
    return (
      <div className="bg-surface border border-border-soft rounded-xl">
        <EmptyState title="No records match these filters" description="Try a different date, batch, or subject." />
      </div>
    );
  }

  return (
    <div className="bg-surface border border-border-soft rounded-xl overflow-hidden overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wider text-text-faint border-b border-border-soft">
            <th className="px-4 py-3 font-medium">Student</th>
            <th className="px-4 py-3 font-medium">Roll No</th>
            <th className="px-4 py-3 font-medium">Time</th>
            <th className="px-4 py-3 font-medium">Recognition</th>
            <th className="px-4 py-3 font-medium">Liveness</th>
            <th className="px-4 py-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-soft">
          {records.map((r) => (
            <tr key={r.id}>
              <td className="px-4 py-3 text-text">{r.studentName}</td>
              <td className="px-4 py-3 font-mono text-text-dim">{r.rollNumber}</td>
              <td className="px-4 py-3 font-mono text-text-dim">{r.time || '—'}</td>
              <td className="px-4 py-3 font-mono text-text-dim">{r.status === 'present' ? `${r.recognitionScore}%` : '—'}</td>
              <td className="px-4 py-3 font-mono text-text-dim">{r.status === 'present' ? `${r.livenessScore}%` : '—'}</td>
              <td className="px-4 py-3">
                <StatusPill tone={r.status === 'present' ? 'verified' : 'blocked'}>
                  {r.status === 'present' ? 'Present' : 'Absent'}
                </StatusPill>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
