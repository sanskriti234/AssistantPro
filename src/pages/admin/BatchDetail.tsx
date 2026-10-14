import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card, CardHeader } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { StatusPill } from '../../components/common/StatusPill';
import { fetchBatch, fetchBatchStudents, generateForm, syncRegistrationForm } from '../../api/batches';
import { ApiError } from '../../api/client';
import type { Batch, StudentRecord, SyncSummary } from '../../types';

export default function BatchDetail() {
  const { id } = useParams();
  const [batch, setBatch] = useState<Batch | null>(null);
  const [studentList, setStudentList] = useState<StudentRecord[]>([]);
  const [generating, setGenerating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [lastSyncResult, setLastSyncResult] = useState<SyncSummary | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchBatch(id).then(setBatch);
    fetchBatchStudents(id).then(setStudentList);
  }, [id]);

  async function handleGenerateForm() {
    if (!id) return;
    setGenerating(true);
    setFormError(null);
    try {
      const updated = await generateForm(id);
      setBatch(updated);
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : 'Could not generate the registration form. Please try again.');
    } finally {
      setGenerating(false);
    }
  }

  async function handleSyncNow() {
    if (!batch?.registrationFormId || !id) return;
    setSyncing(true);
    setSyncError(null);
    try {
      const summary = await syncRegistrationForm(batch.registrationFormId);
      setLastSyncResult(summary);
      const [updatedBatch, updatedStudents] = await Promise.all([fetchBatch(id), fetchBatchStudents(id)]);
      setBatch(updatedBatch);
      setStudentList(updatedStudents);
    } catch (e) {
      setSyncError(e instanceof ApiError ? e.message : 'Could not sync responses. Please try again.');
    } finally {
      setSyncing(false);
    }
  }

  function handleCopyLink() {
    if (!batch?.formUrl) return;
    navigator.clipboard.writeText(batch.formUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  if (!batch) {
    return (
      <AppLayout role="admin" title="Batch">
        <p className="text-sm text-text-dim">Loading…</p>
      </AppLayout>
    );
  }

  return (
    <AppLayout role="admin" title={batch.name}>
      <div className="space-y-4">
        <div className="grid sm:grid-cols-4 gap-3">
          <Card className="p-4"><p className="text-[11px] text-text-faint uppercase">Registered</p><p className="font-mono text-xl mt-1">{batch.registeredStudents}</p></Card>
          <Card className="p-4"><p className="text-[11px] text-text-faint uppercase">Face Enrolled</p><p className="font-mono text-xl mt-1 text-accent">{batch.faceEnrolled}</p></Card>
          <Card className="p-4"><p className="text-[11px] text-text-faint uppercase">Pending Enrollment</p><p className="font-mono text-xl mt-1 text-warning">{batch.pendingEnrollment}</p></Card>
          <Card className="p-4"><p className="text-[11px] text-text-faint uppercase">Today's Attendance</p><p className="font-mono text-xl mt-1 text-verified">{batch.todayAttendancePct}%</p></Card>
        </div>

        <Card>
          <CardHeader
            title="Registration Form"
            action={<StatusPill tone={batch.formStatus === 'active' ? 'verified' : 'neutral'}>{batch.formStatus === 'active' ? '● Active' : 'Inactive'}</StatusPill>}
          />
          <div className="px-5 pb-5 pt-3 space-y-4">
            {batch.formStatus === 'active' && batch.formUrl ? (
              <>
                <div className="flex flex-wrap gap-6 font-mono text-sm">
                  <span>Responses: <span className="text-text">{batch.formResponses}</span></span>
                  <span>Synced: <span className="text-verified">{batch.formSynced}</span></span>
                  <span>Pending: <span className="text-warning">{batch.formPending}</span></span>
                </div>

                <div className="bg-surface-2 border border-border-soft rounded-lg p-3 space-y-2">
                  <p className="text-xs text-text-dim break-all font-mono">{batch.formUrl}</p>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" onClick={handleCopyLink}>{copied ? 'Copied' : 'Copy Link'}</Button>
                    <a href={batch.formUrl} target="_blank" rel="noreferrer">
                      <Button variant="secondary">Open Form</Button>
                    </a>
                  </div>
                  <div className="flex flex-wrap gap-x-6 gap-y-1 text-[11px] text-text-faint pt-1">
                    {batch.googleFormId && <span>Form ID: <span className="font-mono text-text-dim">{batch.googleFormId}</span></span>}
                    {batch.formCreatedAt && <span>Created: <span className="font-mono text-text-dim">{new Date(batch.formCreatedAt).toLocaleDateString()}</span></span>}
                  </div>
                </div>

                <div className="border-t border-border-soft pt-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs text-text-dim">
                        {batch.formLastSyncedAt
                          ? <>Last synced: <span className="font-mono text-text">{new Date(batch.formLastSyncedAt).toLocaleString()}</span></>
                          : 'Never synced yet'}
                      </p>
                    </div>
                    <Button variant="secondary" onClick={handleSyncNow} disabled={syncing}>
                      {syncing ? 'Syncing…' : 'Sync Now'}
                    </Button>
                  </div>
                  {syncError && <p className="text-xs text-blocked">{syncError}</p>}
                  {lastSyncResult && !syncError && (
                    <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] text-text-dim">
                      <span>Found: {lastSyncResult.responsesFound}</span>
                      <span className="text-verified">Synced: {lastSyncResult.synced}</span>
                      <span className="text-warning">Duplicates: {lastSyncResult.duplicates}</span>
                      <span className="text-blocked">Rejected: {lastSyncResult.rejected}</span>
                      <span className="text-blocked">Failed: {lastSyncResult.failed}</span>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="space-y-2">
                <Button onClick={handleGenerateForm} disabled={generating}>
                  {generating ? 'Generating…' : 'Generate registration form'}
                </Button>
                {formError && <p className="text-xs text-blocked">{formError}</p>}
              </div>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Students" subtitle="Accessible only through this batch, per role policy" />
          <div className="overflow-x-auto">
            <table className="w-full text-sm mt-2">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-text-faint border-y border-border-soft">
                  <th className="px-5 py-2.5 font-medium">Name</th>
                  <th className="px-5 py-2.5 font-medium">Roll No</th>
                  <th className="px-5 py-2.5 font-medium">Face Enrollment</th>
                  <th className="px-5 py-2.5 font-medium">Attendance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-soft">
                {studentList.map((s) => (
                  <tr key={s.id}>
                    <td className="px-5 py-3 text-text">{s.name}</td>
                    <td className="px-5 py-3 font-mono text-text-dim">{s.rollNumber}</td>
                    <td className="px-5 py-3">
                      <StatusPill tone={s.faceEnrolled ? 'verified' : 'warning'}>{s.faceEnrolled ? 'Enrolled' : 'Pending'}</StatusPill>
                    </td>
                    <td className="px-5 py-3 font-mono text-text-dim">{s.faceEnrolled ? `${s.overallAttendancePct}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </AppLayout>
  );
}
