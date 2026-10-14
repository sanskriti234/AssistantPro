import type { AttendanceRecord, AttendanceSession, RecognitionResult } from '../types';
import { request } from './client';

export async function startAttendanceSession(input: { batchId: string; subject: string; facultyId: string }): Promise<AttendanceSession> {
  // facultyId is derived from the authenticated user server-side; the
  // parameter is kept so callers don't need to change.
  return request('/attendance/sessions/start', { body: { batchId: input.batchId, subject: input.subject } });
}

export async function endAttendanceSession(sessionId: string): Promise<void> {
  await request(`/attendance/sessions/${sessionId}/end`, { method: 'POST' });
}

// Submits one captured frame for the full backend cycle: SCRFD -> AdaFace ->
// MiniFASNetV2 -> temporal verification -> attendance decision. The
// frontend never computes this decision itself - it only relays the frame
// and displays whatever the backend returns.
export async function submitFrame(session: AttendanceSession, frameDataUrl: string): Promise<RecognitionResult> {
  return request('/attendance/frame', { body: { sessionId: session.id, frame: frameDataUrl } });
}

// No-op kept for API compatibility: de-duplication is enforced by the
// database (uq_attendance_once_per_session), not frontend-side state.
export function resetSessionState() {}

export async function fetchAttendanceHistory(filters: { batchId?: string; date?: string; subject?: string }): Promise<AttendanceRecord[]> {
  const params = new URLSearchParams();
  if (filters.batchId) params.set('batch_id', filters.batchId);
  if (filters.date) params.set('date', filters.date);
  if (filters.subject) params.set('subject', filters.subject);
  const qs = params.toString();
  return request(`/attendance/history${qs ? `?${qs}` : ''}`);
}

export async function fetchStudentAttendance(_studentId: string): Promise<AttendanceRecord[]> {
  return request('/attendance/my-history');
}
