import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { useAuth } from '../../context/AuthContext';
import { fetchStudentDashboard } from '../../api/dashboard';
import type { StudentRecord } from '../../types';

export default function StudentHome() {
  const { user } = useAuth();
  const [record, setRecord] = useState<StudentRecord | null>(null);

  useEffect(() => {
    if (user) fetchStudentDashboard(user.id).then(setRecord);
  }, [user]);

  if (!record) {
    return (
      <AppLayout role="student" title="Home">
        <p className="text-sm text-text-dim">Loading…</p>
      </AppLayout>
    );
  }

  return (
    <AppLayout role="student" title="Home">
      <div className="space-y-4 max-w-md">
        <p className="font-display text-lg font-semibold">Welcome, {record.name.split(' ')[0]}</p>

        {record.faceEnrolled ? (
          <Card className="p-4 flex items-center gap-3 border-verified/30">
            <span className="text-verified text-lg">✓</span>
            <div>
              <p className="text-sm text-text">Face Enrollment Complete</p>
              <p className="text-xs text-text-dim">You're ready for attendance.</p>
            </div>
          </Card>
        ) : (
          <Card className="p-4 border-warning/30">
            <div className="flex items-center gap-3">
              <span className="text-warning text-lg">⚠</span>
              <p className="text-sm text-text">Face Enrollment Required</p>
            </div>
            <p className="text-xs text-text-dim mt-2">Complete face enrollment before attending classes.</p>
            <Link to="/student/enrollment" className="inline-block mt-3 text-xs text-accent hover:underline">
              Start enrollment →
            </Link>
          </Card>
        )}

        <div className="grid grid-cols-2 gap-3">
          <Card className="p-4">
            <p className="text-[11px] text-text-faint uppercase tracking-wider">Today's Attendance</p>
            <p className="font-mono text-lg mt-1.5">{record.faceEnrolled ? 'Not Applicable' : '—'}</p>
          </Card>
          <Card className="p-4">
            <p className="text-[11px] text-text-faint uppercase tracking-wider">Overall Attendance</p>
            <p className="font-mono text-lg mt-1.5 text-verified">{record.overallAttendancePct}%</p>
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}
