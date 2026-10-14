import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { LiveAttendanceView } from '../../components/attendance/LiveAttendanceView';
import { RecentVerifiedList } from '../../components/attendance/RecentVerifiedList';
import { useAttendanceSession } from '../../hooks/useAttendanceSession';
import { useCamera } from '../../hooks/useCamera';
import { useAuth } from '../../context/AuthContext';
import { fetchAssignedBatches } from '../../api/batches';
import type { Batch } from '../../types';

export default function LiveAttendance() {
  const { user } = useAuth();
  const location = useLocation() as { state?: { batchId?: string; subject?: string } };
  const { status, session, recognitionResult, recentVerified, error, startSession, stopSession } = useAttendanceSession();
  const camera = useCamera('environment');

  const [batches, setBatches] = useState<Batch[]>([]);
  const [batchId, setBatchId] = useState(location.state?.batchId ?? '');
  const [subject, setSubject] = useState(location.state?.subject ?? '');

  useEffect(() => {
    if (user) fetchAssignedBatches(user.id).then((b) => {
      setBatches(b);
      if (!batchId && b[0]) setBatchId(b[0].id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function handleStart() {
    if (!user || !batchId || !subject.trim()) return;
    await startSession({ batchId, subject: subject.trim(), facultyId: user.id }, camera.captureFrame);
  }

  const setupPhase = status === 'idle' || status === 'starting';

  return (
    <AppLayout role="faculty" title="Live Attendance">
      {setupPhase ? (
        <Card className="max-w-md p-5 space-y-4">
          <div>
            <label className="text-xs text-text-dim">Batch</label>
            <select
              value={batchId}
              onChange={(e) => setBatchId(e.target.value)}
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent"
            >
              {batches.map((b) => <option key={b.id} value={b.id}>{b.name} — Section {b.section}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-text-dim">Subject / Class</label>
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Machine Learning"
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent"
            />
          </div>
          {error && <p className="text-xs text-blocked">{error}</p>}
          <Button className="w-full" disabled={status === 'starting' || !batchId || !subject.trim()} onClick={handleStart}>
            {status === 'starting' ? 'Starting session…' : 'Start Attendance'}
          </Button>
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-display text-sm font-semibold">{session?.batchName} — {session?.subject}</p>
              <p className="text-xs text-text-dim">{status === 'active' ? 'Session Active' : status === 'ending' ? 'Ending…' : 'Session Ended'}</p>
            </div>
            {status === 'active' && (
              <Button variant="danger" onClick={stopSession}>End Attendance</Button>
            )}
          </div>

          {session && status !== 'ended' && (
            <LiveAttendanceView
              session={session}
              result={recognitionResult}
              videoRef={camera.videoRef}
              ready={camera.ready}
              error={camera.error}
            />
          )}

          {status === 'ended' && session && (
            <Card className="p-6 text-center max-w-sm mx-auto">
              <p className="font-display text-sm font-semibold">Session ended</p>
              <p className="text-xs text-text-dim mt-2">{session.present} present · {session.absent} absent · {session.total} total</p>
            </Card>
          )}

          {status === 'active' && (
            <div>
              <p className="text-xs text-text-faint uppercase tracking-wider mb-2">Recently Verified</p>
              <RecentVerifiedList items={recentVerified} />
            </div>
          )}
        </div>
      )}
    </AppLayout>
  );
}
