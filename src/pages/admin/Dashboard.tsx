import { useEffect, useState } from 'react';
import { AppLayout } from '../../components/layout/AppLayout';
import { StatCard } from '../../components/common/StatCard';
import { Card, CardHeader } from '../../components/common/Card';
import { fetchAdminDashboard } from '../../api/dashboard';
import type { Batch, DashboardStats } from '../../types';

export default function AdminDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [trend, setTrend] = useState<{ day: string; pct: number }[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);

  useEffect(() => {
    fetchAdminDashboard().then((d) => {
      setStats(d.stats);
      setTrend(d.trend);
      setBatches(d.batches);
    });
  }, []);

  return (
    <AppLayout role="admin" title="Dashboard">
      {!stats ? (
        <p className="text-sm text-text-dim">Loading…</p>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <StatCard label="Total Students" value={stats.totalStudents} />
            <StatCard label="Registered" value={stats.registeredStudents} />
            <StatCard label="Face Enrolled" value={stats.faceEnrolledStudents} tone="accent" />
            <StatCard label="Today's Attendance" value={`${stats.todayAttendancePct}%`} tone="verified" />
            <StatCard label="Spoof Attempts" value={stats.spoofAttempts} tone="blocked" />
          </div>

          <div className="grid lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader title="Attendance Trend" subtitle="Last 6 days, institution-wide" />
              <div className="px-5 pb-5 pt-4 flex items-end gap-3 h-36">
                {trend.map((t) => (
                  <div key={t.day} className="flex-1 flex flex-col items-center gap-2">
                    <div className="w-full rounded-t-md bg-gradient-to-t from-accent-2 to-accent" style={{ height: `${t.pct}%` }} />
                    <span className="text-[10px] text-text-faint">{t.day}</span>
                  </div>
                ))}
              </div>
            </Card>

            <Card>
              <CardHeader title="Batch / Department Attendance" />
              <div className="px-5 pb-5 pt-4 space-y-3">
                {batches.filter((b) => b.formStatus === 'active').map((b) => (
                  <div key={b.id}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-text-dim">{b.name}</span>
                      <span className="font-mono text-text">{b.todayAttendancePct}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-surface-3 overflow-hidden">
                      <div className="h-full bg-accent" style={{ width: `${b.todayAttendancePct}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <Card>
            <CardHeader title="Recent Attendance" subtitle="Most recent verified check-ins across all batches" />
            <div className="px-5 pb-5 pt-2 text-xs text-text-dim">
              Detailed records are available under Attendance.
            </div>
          </Card>
        </div>
      )}
    </AppLayout>
  );
}
