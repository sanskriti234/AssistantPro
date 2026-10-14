import type { AcademicSession, Batch, FacultyRecord, StudentRecord, SyncSummary } from '../types';
import { request } from './client';

export async function fetchSessions(): Promise<AcademicSession[]> {
  return request('/sessions');
}

export async function toggleSession(id: string): Promise<AcademicSession[]> {
  return request(`/sessions/${id}/toggle`, { method: 'POST' });
}

export async function createSession(label: string): Promise<AcademicSession[]> {
  return request('/sessions', { body: { label } });
}

export async function fetchBatches(sessionId?: string): Promise<Batch[]> {
  const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
  return request(`/batches${qs}`);
}

export async function fetchBatch(id: string): Promise<Batch | null> {
  try {
    return await request<Batch>(`/batches/${id}`);
  } catch {
    return null;
  }
}

export async function createBatch(input: Omit<Batch, 'id' | 'registeredStudents' | 'faceEnrolled' | 'pendingEnrollment' | 'todayAttendancePct' | 'formResponses' | 'formSynced' | 'formPending' | 'formStatus'>): Promise<Batch> {
  return request('/batches', { body: input });
}

// Throws ApiError (see api/client.ts) on failure - e.g. Google Forms not
// configured (503) or a Google API failure (502) - so the caller can show
// the admin a real reason instead of a silent no-op.
export async function generateForm(batchId: string): Promise<Batch> {
  return request<Batch>(`/batches/${batchId}/generate-form`, { method: 'POST' });
}

// Pulls new responses for this one form via the live Google Forms API and
// normalizes them into student records. Safe to call repeatedly.
export async function syncRegistrationForm(registrationFormId: string): Promise<SyncSummary> {
  return request<SyncSummary>(`/registration/forms/${registrationFormId}/sync`, { method: 'POST' });
}

export async function fetchBatchStudents(batchId: string): Promise<StudentRecord[]> {
  return request(`/batches/${batchId}/students`);
}

export async function fetchFacultyList(): Promise<FacultyRecord[]> {
  return request('/faculty');
}

export async function fetchAssignedBatches(facultyId: string): Promise<Batch[]> {
  return request(`/faculty/${facultyId}/batches`);
}
