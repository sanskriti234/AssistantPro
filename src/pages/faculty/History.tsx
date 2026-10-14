import { useEffect, useState } from 'react';
import { AppLayout } from '../../components/layout/AppLayout';
import { RecordsTable } from '../../components/attendance/RecordsTable';
import { useAuth } from '../../context/AuthContext';
import { fetchAssignedBatches } from '../../api/batches';
import { fetchAttendanceHistory } from '../../api/attendance';
import type { AttendanceRecord, Batch } from '../../types';

export default function FacultyHistory() {
  const { user } = useAuth();
  const [batches, setBatches] = useState<Batch[]>([]);
  const [batchId, setBatchId] = useState('');
  const [date, setDate] = useState('');
  const [records, setRecords] = useState<AttendanceRecord[]>([]);

  useEffect(() => {
    if (user) fetchAssignedBatches(user.id).then(setBatches);
  }, [user]);

  useEffect(() => {
    fetchAttendanceHistory({ batchId: batchId || undefined, date: date || undefined }).then(setRecords);
  }, [batchId, date]);

  return (
    <AppLayout role="faculty" title="Attendance History">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-3">
          <select
            value={batchId}
            onChange={(e) => setBatchId(e.target.value)}
            className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent"
          >
            <option value="">All my batches</option>
            {batches.map((b) => <option key={b.id} value={b.id}>{b.name} — Section {b.section}</option>)}
          </select>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </div>

        <RecordsTable records={records} />
      </div>
    </AppLayout>
  );
}
