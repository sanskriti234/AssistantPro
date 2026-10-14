import { useEffect, useState } from 'react';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { useAuth } from '../../context/AuthContext';
import { fetchStudentDashboard } from '../../api/dashboard';
import type { StudentRecord } from '../../types';

const rows: { key: keyof StudentRecord; label: string }[] = [
  { key: 'name', label: 'Name' },
  { key: 'rollNumber', label: 'Roll Number' },
  { key: 'department', label: 'Department' },
  { key: 'section', label: 'Section' },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
];

export default function Profile() {
  const { user } = useAuth();
  const [record, setRecord] = useState<StudentRecord | null>(null);

  useEffect(() => {
    if (user) fetchStudentDashboard(user.id).then(setRecord);
  }, [user]);

  return (
    <AppLayout role="student" title="My Profile">
      <Card className="max-w-md divide-y divide-border-soft">
        {record && rows.map((r) => (
          <div key={r.key} className="flex items-center justify-between px-5 py-3.5">
            <span className="text-xs text-text-dim">{r.label}</span>
            <span className="text-sm text-text">{record[r.key] as string}</span>
          </div>
        ))}
      </Card>
    </AppLayout>
  );
}
