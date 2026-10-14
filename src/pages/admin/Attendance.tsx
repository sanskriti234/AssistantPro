import { useEffect, useState } from 'react';
import { AppLayout } from '../../components/layout/AppLayout';
import { RecordsTable } from '../../components/attendance/RecordsTable';
import { fetchBatches } from '../../api/batches';
import { fetchAttendanceHistory } from '../../api/attendance';
import type { AttendanceRecord, Batch } from '../../types';

export default function AdminAttendance() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [batchId, setBatchId] = useState('');
  const [records, setRecords] = useState<AttendanceRecord[]>([]);

  useEffect(() => {
    fetchBatches().then(setBatches);
  }, []);

  useEffect(() => {
    fetchAttendanceHistory({ batchId: batchId || undefined }).then(setRecords);
  }, [batchId]);

  return (
    <AppLayout role="admin" title="Attendance">
      <div className="space-y-4">
        <select
          value={batchId}
          onChange={(e) => setBatchId(e.target.value)}
          className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent"
        >
          <option value="">All batches</option>
          {batches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>

        <RecordsTable records={records} />
      </div>
    </AppLayout>
  );
}
