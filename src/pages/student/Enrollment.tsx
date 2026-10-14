import { useState } from 'react';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { EnrollmentCapture } from '../../components/enrollment/EnrollmentCapture';
import { useAuth } from '../../context/AuthContext';
import type { EnrollmentResult } from '../../types';

export default function Enrollment() {
  const { user } = useAuth();
  const [phase, setPhase] = useState<'intro' | 'capturing' | 'done'>('intro');
  const [result, setResult] = useState<EnrollmentResult | null>(null);

  if (!user) return null;

  return (
    <AppLayout role="student" title="Face Enrollment">
      <div className="max-w-sm mx-auto">
        {phase === 'intro' && (
          <Card className="p-5 space-y-4">
            <p className="text-sm text-text">We'll capture several samples of your face from different angles to build your attendance profile.</p>
            <ul className="text-xs text-text-dim space-y-1.5">
              <li>• Find a well-lit space</li>
              <li>• Hold your phone at eye level</li>
              <li>• Look directly at the camera</li>
            </ul>
            <Button className="w-full" onClick={() => setPhase('capturing')}>Begin enrollment</Button>
          </Card>
        )}

        {phase === 'capturing' && (
          <EnrollmentCapture
            studentId={user.id}
            onDone={(r) => {
              setResult(r);
              setPhase('done');
            }}
          />
        )}

        {phase === 'done' && result && (
          <Card className="p-6 text-center rise-in">
            {result.status === 'complete' ? (
              <>
                <p className="text-verified text-2xl">✓</p>
                <p className="font-display text-sm font-semibold mt-2">Face Enrollment Complete</p>
                <div className="text-xs text-text-dim mt-3 space-y-1 font-mono">
                  <p>Samples processed: {result.samplesProcessed}</p>
                  <p>Valid samples: {result.validSamples}</p>
                  <p>Face template: Generated</p>
                </div>
                <p className="text-xs text-text-dim mt-3">You are ready for attendance.</p>
              </>
            ) : (
              <>
                <p className="text-blocked text-2xl">⚠</p>
                <p className="font-display text-sm font-semibold mt-2">Enrollment could not be completed</p>
                <p className="text-xs text-text-dim mt-2">{result.reason}</p>
                <Button className="w-full mt-4" onClick={() => setPhase('capturing')}>Try again</Button>
              </>
            )}
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
