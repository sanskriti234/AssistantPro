import { useState } from 'react';
import { useCamera } from '../../hooks/useCamera';
import { CameraView } from '../camera/CameraView';
import { Button } from '../common/Button';
import { finalizeEnrollment, REQUIRED_SAMPLES, validateSample } from '../../api/enrollment';
import type { EnrollmentResult } from '../../types';

export function EnrollmentCapture({ studentId, onDone }: { studentId: string; onDone: (result: EnrollmentResult) => void }) {
  const { videoRef, ready, error, captureFrame } = useCamera('user');
  const [captured, setCaptured] = useState(0);
  const [valid, setValid] = useState(0);
  const [status, setStatus] = useState<'idle' | 'capturing' | 'processing'>('idle');
  const [feedback, setFeedback] = useState<string | null>(null);

  async function runCapture() {
    setStatus('capturing');
    let validCount = 0;
    for (let i = 1; i <= REQUIRED_SAMPLES; i++) {
      const frame = captureFrame();
      setCaptured(i);
      if (frame) {
        const result = await validateSample(frame);
        if (result.accepted) {
          validCount += 1;
          setValid(validCount);
          setFeedback(null);
        } else {
          setFeedback(result.reason ?? 'Sample rejected');
        }
      }
      await new Promise((r) => setTimeout(r, 120));
    }
    setStatus('processing');
    const result = await finalizeEnrollment(studentId, validCount);
    onDone(result);
  }

  const progressPct = (captured / REQUIRED_SAMPLES) * 100;

  return (
    <div className="max-w-sm mx-auto">
      <CameraView
        videoRef={videoRef}
        ready={ready}
        error={error}
        guideLabel={status === 'idle' ? 'Look at the camera' : undefined}
      />

      {status !== 'idle' && (
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-dim">{status === 'capturing' ? 'Capturing…' : 'Processing on backend…'}</span>
            <span className="font-mono text-xs text-accent">{captured} / {REQUIRED_SAMPLES}</span>
          </div>
          <p className="text-[11px] text-text-faint font-mono">{valid} valid so far</p>
          <div className="h-1.5 rounded-full bg-surface-3 overflow-hidden">
            <div className="h-full bg-gradient-to-r from-accent to-accent-2 transition-all duration-150" style={{ width: `${progressPct}%` }} />
          </div>
          {feedback && <p className="text-xs text-warning">{feedback}</p>}
        </div>
      )}

      <div className="mt-5 space-y-2 text-xs text-text-dim">
        <p className="flex items-center gap-2"><span className="text-verified">✓</span> Face detected</p>
        <p className="flex items-center gap-2"><span className="text-verified">✓</span> Good lighting</p>
        <p className="flex items-center gap-2"><span className="text-verified">✓</span> Face centered</p>
      </div>

      {status === 'idle' && (
        <Button className="w-full mt-5" disabled={!ready} onClick={runCapture}>
          Start capture
        </Button>
      )}
    </div>
  );
}
