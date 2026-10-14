import { useEffect, useState } from 'react';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { useAuth } from '../../context/AuthContext';
import { fetchAssignedBatches } from '../../api/batches';
import type { Batch } from '../../types';

export default function MyBatches() {
  const { user } = useAuth();
  const [batches, setBatches] = useState<Batch[]>([]);

  useEffect(() => {
    if (user) fetchAssignedBatches(user.id).then(setBatches);
  }, [user]);

  return (
    <AppLayout role="faculty" title="My Batches">
      <div className="grid sm:grid-cols-2 gap-3">
        {batches.map((b) => (
          <Card key={b.id} className="p-4">
            <p className="font-display text-sm font-semibold">{b.name}</p>
            <p className="text-xs text-text-dim mt-0.5">{b.department} · Section {b.section}</p>
            <div className="grid grid-cols-2 gap-2 mt-4 text-center">
              <div>
                <p className="font-mono text-sm">{b.registeredStudents}</p>
                <p className="text-[10px] text-text-faint">Students</p>
              </div>
              <div>
                <p className="font-mono text-sm text-verified">{b.todayAttendancePct}%</p>
                <p className="text-[10px] text-text-faint">Today</p>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </AppLayout>
  );
}
