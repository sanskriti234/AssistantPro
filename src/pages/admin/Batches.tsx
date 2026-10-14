import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { StatusPill } from '../../components/common/StatusPill';
import { createBatch, fetchBatches, fetchSessions } from '../../api/batches';
import type { AcademicSession, Batch } from '../../types';

export default function Batches() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [sessions, setSessions] = useState<AcademicSession[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', department: '', year: 1, section: 'A', sessionId: '' });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchBatches().then(setBatches);
    fetchSessions().then((s) => {
      setSessions(s);
      setForm((f) => ({ ...f, sessionId: s.find((x) => x.active)?.id ?? s[0]?.id ?? '' }));
    });
  }, []);

  async function handleCreate() {
    if (!form.name.trim() || !form.department.trim() || !form.sessionId) return;
    setCreating(true);
    const batch = await createBatch(form);
    setBatches((prev) => [...prev, batch]);
    setShowForm(false);
    setForm((f) => ({ ...f, name: '', department: '' }));
    setCreating(false);
  }

  return (
    <AppLayout role="admin" title="Batches">
      <div className="space-y-4">
        <div className="flex justify-end">
          <Button onClick={() => setShowForm((v) => !v)}>{showForm ? 'Cancel' : 'Create batch'}</Button>
        </div>

        {showForm && (
          <Card className="p-4 grid sm:grid-cols-2 gap-3">
            <input placeholder="Batch name (e.g. CSE AIML 2027)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent" />
            <input placeholder="Department" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent" />
            <input type="number" placeholder="Year" value={form.year} onChange={(e) => setForm({ ...form, year: Number(e.target.value) })} className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent" />
            <input placeholder="Section" value={form.section} onChange={(e) => setForm({ ...form, section: e.target.value })} className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent" />
            <select value={form.sessionId} onChange={(e) => setForm({ ...form, sessionId: e.target.value })} className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent sm:col-span-2">
              {sessions.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
            <Button className="sm:col-span-2" onClick={handleCreate} disabled={creating}>Save batch</Button>
          </Card>
        )}

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {batches.map((b) => (
            <Link key={b.id} to={`/admin/batches/${b.id}`}>
              <Card className="p-4 h-full hover:border-accent/40 transition-colors">
                <div className="flex items-center justify-between">
                  <p className="font-display text-sm font-semibold">{b.name}</p>
                  <StatusPill tone={b.formStatus === 'active' ? 'verified' : 'neutral'}>{b.formStatus}</StatusPill>
                </div>
                <p className="text-xs text-text-dim mt-1">{b.department} · Section {b.section}</p>

                <div className="grid grid-cols-3 gap-2 mt-4 text-center">
                  <div>
                    <p className="font-mono text-sm">{b.registeredStudents}</p>
                    <p className="text-[10px] text-text-faint">Registered</p>
                  </div>
                  <div>
                    <p className="font-mono text-sm text-accent">{b.faceEnrolled}</p>
                    <p className="text-[10px] text-text-faint">Enrolled</p>
                  </div>
                  <div>
                    <p className="font-mono text-sm text-warning">{b.pendingEnrollment}</p>
                    <p className="text-[10px] text-text-faint">Pending</p>
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </AppLayout>
  );
}
