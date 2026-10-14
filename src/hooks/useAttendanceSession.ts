import { useCallback, useRef, useState } from 'react';
import type { AttendanceSession, RecognitionResult } from '../types';
import { endAttendanceSession, resetSessionState, startAttendanceSession, submitFrame } from '../api/attendance';

export type SessionStatus = 'idle' | 'starting' | 'active' | 'ending' | 'ended';

const FRAME_INTERVAL_MS = 1200;

export function useAttendanceSession() {
  const [status, setStatus] = useState<SessionStatus>('idle');
  const [session, setSession] = useState<AttendanceSession | null>(null);
  const [recognitionResult, setRecognitionResult] = useState<RecognitionResult | null>(null);
  const [recentVerified, setRecentVerified] = useState<RecognitionResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const loopRef = useRef<boolean>(false);

  const runLoop = useCallback(async (activeSession: AttendanceSession, getFrame: () => string | null) => {
    loopRef.current = true;
    while (loopRef.current) {
      const frame = getFrame();
      if (!frame) {
        await new Promise((r) => setTimeout(r, 300));
        continue;
      }
      try {
        const result = await submitFrame(activeSession, frame);
        setRecognitionResult(result);
        if (result.status === 'verified') {
          setSession((prev) => (prev ? { ...prev, present: prev.present + 1, absent: Math.max(0, prev.absent - 1) } : prev));
          setRecentVerified((prev) => [result, ...prev].slice(0, 8));
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Recognition pipeline error');
      }
      await new Promise((r) => setTimeout(r, FRAME_INTERVAL_MS));
    }
  }, []);

  async function startSession(
    input: { batchId: string; subject: string; facultyId: string },
    getFrame: () => string | null
  ) {
    setStatus('starting');
    setError(null);
    resetSessionState();
    try {
      const s = await startAttendanceSession(input);
      setSession(s);
      setStatus('active');
      runLoop(s, getFrame);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start session');
      setStatus('idle');
    }
  }

  async function stopSession() {
    if (!session) return;
    setStatus('ending');
    loopRef.current = false;
    await endAttendanceSession(session.id);
    setStatus('ended');
  }

  return { status, session, recognitionResult, recentVerified, error, startSession, stopSession };
}
