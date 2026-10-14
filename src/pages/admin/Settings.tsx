import { useEffect, useState } from 'react';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card, CardHeader } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { fetchSettings, updateSettings } from '../../api/settings';
import type { SystemSettings } from '../../types';

const fields: { key: keyof SystemSettings; label: string; suffix?: string }[] = [
  { key: 'recognitionThreshold', label: 'Recognition Threshold', suffix: '%' },
  { key: 'livenessThreshold', label: 'Liveness Threshold', suffix: '%' },
  { key: 'faceQualityThreshold', label: 'Face Quality Threshold', suffix: '%' },
  { key: 'attendanceCooldownSeconds', label: 'Attendance Cooldown', suffix: 's' },
];

export default function Settings() {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchSettings().then(setSettings);
  }, []);

  async function handleSave() {
    if (!settings) return;
    setSaving(true);
    const updated = await updateSettings(settings);
    setSettings(updated);
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  if (!settings) {
    return (
      <AppLayout role="admin" title="Settings">
        <p className="text-sm text-text-dim">Loading…</p>
      </AppLayout>
    );
  }

  return (
    <AppLayout role="admin" title="Settings">
      <Card className="max-w-lg">
        <CardHeader title="Recognition & Liveness" subtitle="These thresholds govern the backend attendance decision" />
        <div className="px-5 pb-5 pt-4 space-y-4">
          {fields.map((f) => (
            <div key={f.key}>
              <div className="flex justify-between text-xs mb-1.5">
                <label className="text-text-dim">{f.label}</label>
                <span className="font-mono text-accent">{settings[f.key]}{f.suffix}</span>
              </div>
              <input
                type="range"
                min={f.key === 'attendanceCooldownSeconds' ? 60 : 50}
                max={f.key === 'attendanceCooldownSeconds' ? 1800 : 100}
                value={settings[f.key]}
                onChange={(e) => setSettings({ ...settings, [f.key]: Number(e.target.value) })}
                className="w-full accent-accent"
              />
            </div>
          ))}

          <div>
            <label className="text-xs text-text-dim">Camera Resolution</label>
            <select
              value={settings.cameraResolution}
              onChange={(e) => setSettings({ ...settings, cameraResolution: e.target.value })}
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm outline-none focus:border-accent"
            >
              <option value="1280x720">1280 × 720</option>
              <option value="1920x1080">1920 × 1080</option>
            </select>
          </div>

          <Button onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : saved ? 'Saved' : 'Save settings'}
          </Button>
        </div>
      </Card>
    </AppLayout>
  );
}
