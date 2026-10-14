import type { RefObject } from 'react';
import { CameraView } from '../camera/CameraView';
import { StatusPill } from '../common/StatusPill';
import type { AttendanceSession, RecognitionResult } from '../../types';

const statusCopy: Record<RecognitionResult['status'], { label: string; tone: 'verified' | 'blocked' | 'warning' | 'neutral' | 'accent' }> = {
  verified: { label: 'Verified', tone: 'verified' },
  unknown: { label: 'Unknown Student', tone: 'warning' },
  spoof: { label: 'Presentation Attack Detected', tone: 'blocked' },
  multiple_faces: { label: 'Multiple Faces Detected', tone: 'warning' },
  poor_quality: { label: 'Face Quality Too Low', tone: 'neutral' },
  already_marked: { label: 'Already Marked', tone: 'accent' },
};

export function LiveAttendanceView({
  session,
  result,
  videoRef,
  ready,
  error,
}: {
  session: AttendanceSession;
  result: RecognitionResult | null;
  videoRef: RefObject<HTMLVideoElement | null>;
  ready: boolean;
  error: string | null;
}) {
  return (
    <div className="grid md:grid-cols-[1fr_320px] gap-5">
      <div className="relative">
        <CameraView videoRef={videoRef} ready={ready} error={error} aspect="aspect-video" />

        {result && (
          <div className="absolute left-4 bottom-4 right-4 rise-in">
            <div className="bg-base/85 backdrop-blur border border-border-soft rounded-xl px-4 py-3">
              <div className="flex items-center justify-between">
                <div>
                  {result.studentName ? (
                    <>
                      <p className="font-display text-sm font-semibold">{result.studentName}</p>
                      <p className="font-mono text-xs text-text-dim">{result.rollNumber}</p>
                    </>
                  ) : (
                    <p className="font-display text-sm font-semibold text-text-dim">No identity match</p>
                  )}
                </div>
                <StatusPill tone={statusCopy[result.status].tone}>
                  {statusCopy[result.status].label}
                </StatusPill>
              </div>
              {result.status === 'verified' && (
                <div className="flex gap-5 mt-2 font-mono text-xs text-text-dim">
                  <span>Recognition <span className="text-accent">{result.recognitionScore}%</span></span>
                  <span>Liveness <span className="text-accent">{result.livenessScore}%</span></span>
                </div>
              )}
              {result.status === 'already_marked' && (
                <p className="mt-1 font-mono text-xs text-text-dim">Marked at {result.markedAt}</p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="space-y-4">
        <div className="bg-surface border border-border-soft rounded-xl p-4">
          <p className="text-xs text-text-faint uppercase tracking-wider mb-3">Class Count</p>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <p className="font-mono text-xl text-verified">{session.present}</p>
              <p className="text-[11px] text-text-dim">Present</p>
            </div>
            <div>
              <p className="font-mono text-xl text-text-dim">{session.absent}</p>
              <p className="text-[11px] text-text-dim">Absent</p>
            </div>
            <div>
              <p className="font-mono text-xl text-text">{session.total}</p>
              <p className="text-[11px] text-text-dim">Total</p>
            </div>
          </div>
        </div>

        <div className="bg-surface border border-border-soft rounded-xl p-4">
          <p className="text-xs text-text-faint uppercase tracking-wider mb-3">Pipeline</p>
          <p className="font-mono text-xs text-accent">Detect → Recognize → Verify → Record</p>
        </div>
      </div>
    </div>
  );
}
