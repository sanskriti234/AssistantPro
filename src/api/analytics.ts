import { request } from './client';

interface InstitutionAnalytics {
  trend: { day: string; pct: number }[];
  byDepartment: { department: string; avgPct: number }[];
  byBatch: { name: string; pct: number }[];
  recognitionSuccessPct: number;
  spoofAttempts: number;
}

interface FacultyAnalytics {
  trend: { day: string; pct: number }[];
  byBatch: { name: string; pct: number }[];
}

export async function fetchInstitutionAnalytics(): Promise<InstitutionAnalytics> {
  return request('/analytics/institution');
}

export async function fetchBatchAnalytics(_batchIds: string[]): Promise<FacultyAnalytics> {
  // Backend derives "my batches" from the authenticated faculty member via
  // the token rather than an id list passed from the client.
  return request('/analytics/faculty');
}
