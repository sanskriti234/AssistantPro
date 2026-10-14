import { useEffect, useState } from 'react';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card, CardHeader } from '../../components/common/Card';
import { StatCard } from '../../components/common/StatCard';
import { fetchInstitutionAnalytics } from '../../api/analytics';

type Data = Awaited<ReturnType<typeof fetchInstitutionAnalytics>>;

export default function AdminAnalytics() {
  const [data, setData] = useState<Data | null>(null);

  useEffect(() => {
    fetchInstitutionAnalytics().then(setData);
  }, []);

  if (!data) {
    return (
      <AppLayout role="admin" title="Analytics">
        <p className="text-sm text-text-dim">Loading…</p>
      </AppLayout>
    );
  }

  return (
    <AppLayout role="admin" title="Analytics">
      <div className="space-y-6">
        <div className="grid grid-cols-2 sm:grid-cols-2 gap-3">
          <StatCard label="Recognition Success" value={`${data.recognitionSuccessPct}%`} tone="verified" />
          <StatCard label="Spoof Attempts" value={data.spoofAttempts} tone="blocked" />
        </div>

        <Card>
          <CardHeader title="Department Attendance" />
          <div className="px-5 pb-5 pt-4 space-y-3">
            {data.byDepartment.map((d) => (
              <div key={d.department}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-text-dim">{d.department}</span>
                  <span className="font-mono text-text">{d.avgPct}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-surface-3 overflow-hidden">
                  <div className="h-full bg-accent-2" style={{ width: `${d.avgPct}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Batch Attendance" />
          <div className="px-5 pb-5 pt-4 space-y-3">
            {data.byBatch.map((b) => (
              <div key={b.name}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-text-dim">{b.name}</span>
                  <span className="font-mono text-text">{b.pct}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-surface-3 overflow-hidden">
                  <div className="h-full bg-accent" style={{ width: `${b.pct}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </AppLayout>
  );
}
