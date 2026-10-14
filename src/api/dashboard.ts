import type { Batch, ClassSlot, DashboardStats, StudentRecord } from '../types';
import { request } from './client';

export async function fetchAdminDashboard(): Promise<{ stats: DashboardStats; trend: { day: string; pct: number }[]; batches: Batch[] }> {
  return request('/dashboard/admin');
}

export async function fetchFacultyDashboard(): Promise<{ classSlots: ClassSlot[] }> {
  return request('/dashboard/faculty');
}

export async function fetchStudentDashboard(_studentId: string): Promise<StudentRecord | null> {
  try {
    return await request<StudentRecord>('/dashboard/student');
  } catch {
    return null;
  }
}
