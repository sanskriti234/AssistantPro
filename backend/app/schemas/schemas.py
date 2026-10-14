from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from uuid import UUID


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


# ---- Auth / User -----------------------------------------------------------

class UserOut(CamelModel):
    id: str
    name: str
    role: str  # 'admin' | 'faculty' | 'student' (lowercased for the frontend)
    email: str
    rollNumber: str | None = None
    batchId: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(CamelModel):
    user: UserOut
    accessToken: str
    mustChangePassword: bool = False


# ---- Academic sessions / batches ------------------------------------------

class AcademicSessionOut(CamelModel):
    id: str
    label: str
    active: bool
    batchIds: list[str]


class CreateSessionRequest(BaseModel):
    label: str


class BatchOut(CamelModel):
    id: str
    name: str
    department: str
    year: int
    section: str
    sessionId: str
    registeredStudents: int
    faceEnrolled: int
    pendingEnrollment: int
    todayAttendancePct: float
    formStatus: str  # 'active' | 'inactive'
    formResponses: int
    formSynced: int
    formPending: int
    formUrl: str | None = None
    googleFormId: str | None = None
    formCreatedAt: str | None = None
    registrationFormId: str | None = None
    formLastSyncedAt: str | None = None


class CreateBatchRequest(BaseModel):
    name: str
    department: str
    year: int
    section: str
    sessionId: str


class StudentRecordOut(CamelModel):
    id: str
    name: str
    rollNumber: str
    department: str
    batchId: str
    section: str
    email: str
    phone: str
    faceEnrolled: bool
    overallAttendancePct: float


class FacultyRecordOut(CamelModel):
    id: str
    name: str
    email: str
    assignedBatchIds: list[str]


# ---- Enrollment -------------------------------------------------------------

class ValidateSampleRequest(BaseModel):
    frame: str  # base64 data URL - never persisted, only scored


class ValidateSampleResponse(CamelModel):
    accepted: bool
    reason: str | None = None


class FinalizeEnrollmentRequest(BaseModel):
    validSampleCount: int
    # Embeddings collected during capture, one per accepted sample, so the
    # backend can select/average and persist to pgvector. In production
    # these come from the real AdaFace pipeline - see README limitations.
    embeddings: list[list[float]] = []


class EnrollmentResultOut(CamelModel):
    status: str  # 'complete' | 'failed'
    samplesProcessed: int
    validSamples: int
    reason: str | None = None


# ---- Attendance --------------------------------------------------------------

class StartSessionRequest(BaseModel):
    batchId: str
    subject: str


class AttendanceSessionOut(CamelModel):
    id: str
    batchId: str
    batchName: str
    section: str
    subject: str
    facultyId: str
    startedAt: str
    present: int
    absent: int
    total: int
    active: bool


class SubmitFrameRequest(BaseModel):
    sessionId: str
    frame: str  # base64 data URL - never persisted, only scored


class RecognitionResultOut(CamelModel):
    status: str
    studentName: str | None = None
    rollNumber: str | None = None
    recognitionScore: float | None = None
    livenessScore: float | None = None
    markedAt: str | None = None


class AttendanceRecordOut(CamelModel):
    id: str
    studentId: str
    studentName: str
    rollNumber: str
    batchId: str
    subject: str
    date: str
    time: str
    recognitionScore: float
    livenessScore: float
    status: str  # 'present' | 'absent'


# ---- Dashboard / analytics ---------------------------------------------------

class DashboardStatsOut(CamelModel):
    totalStudents: int
    registeredStudents: int
    faceEnrolledStudents: int
    todayAttendancePct: float
    spoofAttempts: int


class TrendPointOut(CamelModel):
    day: str
    pct: float


class ClassSlotOut(CamelModel):
    id: str
    batchId: str
    batchName: str
    section: str
    subject: str
    time: str
    status: str


# ---- Settings ------------------------------------------------------------

class SystemSettingsOut(CamelModel):
    recognitionThreshold: float
    livenessThreshold: float
    faceQualityThreshold: float
    attendanceCooldownSeconds: int
    cameraResolution: str


class SystemSettingsUpdate(CamelModel):
    recognitionThreshold: float | None = None
    livenessThreshold: float | None = None
    faceQualityThreshold: float | None = None
    attendanceCooldownSeconds: int | None = None
    cameraResolution: str | None = None


# ---- Registration sync (Google Form) --------------------------------------

class RegistrationSubmissionIn(BaseModel):
    """One row from the synced Google Sheet, as delivered by the sync worker."""

    google_response_id: str
    submitted_at: datetime
    raw_response: dict


class FacultyRegistrationRequestCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    employee_id: str = Field(min_length=1, max_length=100)
    email: EmailStr
    department_id: UUID
    designation: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)


class FacultyRegistrationRequestResponse(BaseModel):
    id: UUID
    full_name: str
    employee_id: str
    email: EmailStr
    department_id: UUID
    designation: str | None
    phone: str | None
    status: str
    requested_at: datetime

class FacultyRegistrationRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

# ---- Password reset ---------------------------------------------------------


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(
        min_length=8,
        max_length=128,
    )
    