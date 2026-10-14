import { useEffect, useState } from 'react';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { StatusPill } from '../../components/common/StatusPill';
import { useAuth } from '../../context/AuthContext';
import { fetchStudentAttendance } from '../../api/attendance';
import { fetchStudentDashboard } from '../../api/dashboard';
import type { AttendanceRecord, StudentRecord } from '../../types';

export default function StudentAttendance() {
  const { user } = useAuth();
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [profile, setProfile] = useState<StudentRecord | null>(null);

  useEffect(() => {
    if (!user) return;
    fetchStudentAttendance(user.id).then(setRecords);
    fetchStudentDashboard(user.id).then(setProfile);
  }, [user]);

  const presentCount = records.filter((r) => r.status === 'present').length;
  const absentCount = records.filter((r) => r.status === 'absent').length;

  return (
    <AppLayout role="student" title="My Attendance">
      <div className="max-w-md space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <Card className="p-4 text-center">
            <p className="font-mono text-lg text-verified">{presentCount}</p>
            <p className="text-[10px] text-text-faint mt-1">Present</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="font-mono text-lg text-blocked">{absentCount}</p>
            <p className="text-[10px] text-text-faint mt-1">Absent</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="font-mono text-lg text-accent">{profile?.overallAttendancePct ?? '—'}%</p>
            <p className="text-[10px] text-text-faint mt-1">Percentage</p>
          </Card>
        </div>

        <Card className="divide-y divide-border-soft">
          {records.map((r) => (
            <div key={r.id} className="flex items-center justify-between px-4 py-3">
              <div>
                <p className="text-sm text-text">{r.subject}</p>
                <p className="text-[11px] text-text-dim font-mono">{r.date}</p>
              </div>
              <StatusPill tone={r.status === 'present' ? 'verified' : 'blocked'}>
                {r.status === 'present' ? 'Present' : 'Absent'}
              </StatusPill>
            </div>
          ))}
        </Card>
      </div>
    </AppLayout>
  );
}
