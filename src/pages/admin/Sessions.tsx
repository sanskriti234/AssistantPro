import { useEffect, useState } from 'react';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { StatusPill } from '../../components/common/StatusPill';
import { createSession, fetchSessions, toggleSession } from '../../api/batches';
import type { AcademicSession } from '../../types';

export default function Sessions() {
  const [sessions, setSessions] = useState<AcademicSession[]>([]);
  const [newLabel, setNewLabel] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchSessions().then(setSessions);
  }, []);

  async function handleToggle(id: string) {
    setSessions(await toggleSession(id));
  }

  async function handleCreate() {
    if (!newLabel.trim()) return;
    setCreating(true);
    const updated = await createSession(newLabel.trim());
    setSessions(updated);
    setNewLabel('');
    setCreating(false);
  }

  return (
    <AppLayout role="admin" title="Academic Sessions">
      <div className="space-y-4">
        <Card className="p-4 flex flex-col sm:flex-row gap-3">
          <input
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            placeholder="e.g. 2027–28"
            className="flex-1 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <Button onClick={handleCreate} disabled={creating}>Create session</Button>
        </Card>

        <div className="grid sm:grid-cols-2 gap-3">
          {sessions.map((s) => (
            <Card key={s.id} className="p-4">
              <div className="flex items-center justify-between">
                <p className="font-display text-base font-semibold">{s.label}</p>
                <StatusPill tone={s.active ? 'verified' : 'neutral'}>{s.active ? 'Active' : 'Inactive'}</StatusPill>
              </div>
              <p className="text-xs text-text-dim mt-2">{s.batchIds.length} associated batches</p>
              <Button variant="secondary" className="mt-3 w-full" onClick={() => handleToggle(s.id)}>
                {s.active ? 'Deactivate' : 'Activate'}
              </Button>
            </Card>
          ))}
        </div>
      </div>
    </AppLayout>
  );
}
