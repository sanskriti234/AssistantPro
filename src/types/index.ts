export type Role = 'admin' | 'faculty' | 'student';

export interface User {
  id: string;
  name: string;
  role: Role;
  email: string;
  // present only for student role
  rollNumber?: string;
  batchId?: string;
}

export interface AcademicSession {
  id: string;
  label: string; // e.g. "2026-27"
  active: boolean;
  batchIds: string[];
}

export interface SyncSummary {
  formsChecked?: number;
  responsesFound: number;
  synced: number;
  duplicates: number;
  rejected: number;
  failed: number;
  formsWithErrors?: number;
}

export interface Batch {
  id: string;
  name: string; // e.g. "CSE AIML 2027"
  department: string;
  year: number;
  section: string;
  sessionId: string;
  registeredStudents: number;
  faceEnrolled: number;
  pendingEnrollment: number;
  todayAttendancePct: number;
  formStatus: 'active' | 'inactive';
  formResponses: number;
  formSynced: number;
  formPending: number;
  formUrl?: string | null;
  googleFormId?: string | null;
  formCreatedAt?: string | null;
  registrationFormId?: string | null;
  formLastSyncedAt?: string | null;
}

export interface StudentRecord {
  id: string;
  name: string;
  rollNumber: string;
  department: string;
  batchId: string;
  section: string;
  email: string;
  phone: string;
  faceEnrolled: boolean;
  overallAttendancePct: number;
}

export interface FacultyRecord {
  id: string;
  name: string;
  email: string;
  assignedBatchIds: string[];
}

export interface EnrollmentSample {
  index: number;
  quality: 'good' | 'poor';
}

export interface EnrollmentResult {
  status: 'complete' | 'failed';
  samplesProcessed: number;
  validSamples: number;
  reason?: string;
}

export type ClassSlot = {
  id: string;
  batchId: string;
  batchName: string;
  section: string;
  subject: string;
  time: string;
  status: 'upcoming' | 'active' | 'ended';
};

export type RecognitionStatus =
  | 'verified'
  | 'unknown'
  | 'spoof'
  | 'multiple_faces'
  | 'poor_quality'
  | 'already_marked';

export interface RecognitionResult {
  status: RecognitionStatus;
  studentName?: string;
  rollNumber?: string;
  recognitionScore?: number;
  livenessScore?: number;
  markedAt?: string;
}

export interface AttendanceSession {
  id: string;
  batchId: string;
  batchName: string;
  section: string;
  subject: string;
  facultyId: string;
  startedAt: string;
  present: number;
  absent: number;
  total: number;
  active: boolean;
}

export interface AttendanceRecord {
  id: string;
  studentId: string;
  studentName: string;
  rollNumber: string;
  batchId: string;
  subject: string;
  date: string;
  time: string;
  recognitionScore: number;
  livenessScore: number;
  status: 'present' | 'absent';
}

export interface DashboardStats {
  totalStudents: number;
  registeredStudents: number;
  faceEnrolledStudents: number;
  todayAttendancePct: number;
  spoofAttempts: number;
}

export interface SystemSettings {
  recognitionThreshold: number;
  livenessThreshold: number;
  faceQualityThreshold: number;
  attendanceCooldownSeconds: number;
  cameraResolution: string;
}
