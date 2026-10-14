import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { fetchFacultyDashboard } from '../../api/dashboard';
import type { ClassSlot } from '../../types';

export default function FacultyDashboard() {
  const [classes, setClasses] = useState<ClassSlot[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    fetchFacultyDashboard().then((d) => setClasses(d.classSlots));
  }, []);

  const active = classes.filter((c) => c.status === 'active').length;

  return (
    <AppLayout role="faculty" title="Dashboard">
      <div className="space-y-6">
        <div className="grid grid-cols-3 gap-3">
          <Card className="p-4"><p className="text-[11px] text-text-faint uppercase">Today's Classes</p><p className="font-mono text-xl mt-1">{classes.length}</p></Card>
          <Card className="p-4"><p className="text-[11px] text-text-faint uppercase">Active</p><p className="font-mono text-xl mt-1 text-verified">{active}</p></Card>
          <Card className="p-4"><p className="text-[11px] text-text-faint uppercase">Pending</p><p className="font-mono text-xl mt-1 text-warning">{classes.length - active}</p></Card>
        </div>

        <div className="space-y-3">
          {classes.map((c) => (
            <Card key={c.id} className="p-4 flex items-center justify-between">
              <div>
                <p className="font-display text-sm font-semibold">{c.batchName} — Section {c.section}</p>
                <p className="text-xs text-text-dim mt-1">{c.time} · {c.subject}</p>
              </div>
              <Button onClick={() => navigate('/faculty/live', { state: { batchId: c.batchId, subject: c.subject } })}>
                Start Attendance
              </Button>
            </Card>
          ))}
        </div>
      </div>
    </AppLayout>
  );
}
