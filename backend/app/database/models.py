from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone
from typing import Any
from pydantic import BaseModel
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
    text,
    Enum as SAEnum,
    Column,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.database.base import Base, UUIDPKMixin, TimestampMixin, utcnow


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    FACULTY = "FACULTY"
    STUDENT = "STUDENT"

class SessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class AttendanceSessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class FaceEnrollmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"

class FormStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class ContactType(str, enum.Enum):
    STUDENT = "STUDENT"
    FATHER = "FATHER"
    MOTHER = "MOTHER"
    GUARDIAN = "GUARDIAN"

class EnrollmentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    WITHDRAWN = "WITHDRAWN"

class QualificationType(str, enum.Enum):
    HIGH_SCHOOL = "HIGH_SCHOOL"
    INTERMEDIATE = "INTERMEDIATE"
    DIPLOMA = "DIPLOMA"

class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"

class RecognitionResult(str, enum.Enum):
    VERIFIED = "VERIFIED"
    UNKNOWN = "UNKNOWN"
    SPOOF = "SPOOF"
    POOR_QUALITY = "POOR_QUALITY"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    ALREADY_MARKED = "ALREADY_MARKED"

class SubmissionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"


class AcademicSession(UUIDPKMixin, Base):
    __tablename__ = "academic_sessions"
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[SessionStatus] = mapped_column(SAEnum(SessionStatus, name="academic_session_status"), nullable=False, default=SessionStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    batches: Mapped[list[Batch]] = relationship(back_populates="academic_session", passive_deletes=True)

class Course(UUIDPKMixin, Base):
    __tablename__ = "courses"
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    duration_years: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    batches: Mapped[list[Batch]] = relationship(back_populates="course")

class Department(UUIDPKMixin, Base):
    __tablename__ = "departments"
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    batches: Mapped[list[Batch]] = relationship(back_populates="department")
    faculty: Mapped[list[Faculty]] = relationship(back_populates="department")
    subjects: Mapped[list[Subject]] = relationship(back_populates="department")
    faculty_registration_requests: Mapped[list["FacultyRegistrationRequest"]] = relationship(
    back_populates="department",
    )
class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(SAEnum(Role, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_profile: Mapped[Admin | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    faculty_profile: Mapped[Faculty | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    student_profile: Mapped[Student | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")
    activation_tokens: Mapped[list[AccountActivationToken]] = relationship(back_populates="user", cascade="all, delete-orphan")
    must_change_password: Mapped[bool] = mapped_column(
    default=False,
    nullable=False, 
    )

class Admin(Base):
    __tablename__ = "admins"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    user: Mapped[User] = relationship(back_populates="admin_profile")

class AuditLog(UUIDPKMixin, Base):
    __tablename__ = "audit_logs"
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    ) 
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    user: Mapped[User | None] = relationship(back_populates="audit_logs")

class Batch(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "batches"
    academic_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    academic_session: Mapped[AcademicSession] = relationship(back_populates="batches")
    course: Mapped[Course] = relationship(back_populates="batches")
    department: Mapped[Department] = relationship(back_populates="batches")
    faculty_links: Mapped[list[FacultyBatch]] = relationship(back_populates="batch", cascade="all, delete-orphan")
    enrollments: Mapped[list[StudentEnrollment]] = relationship(back_populates="batch")
    attendance_sessions: Mapped[list[AttendanceSession]] = relationship(back_populates="batch")
    registration_form: Mapped[RegistrationForm | None] = relationship(back_populates="batch", uselist=False, cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("academic_session_id", "course_id", "department_id", "year", "section", name="uq_batch_identity"),)

class Faculty(Base):
    __tablename__ = "faculty"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    user: Mapped[User] = relationship(back_populates="faculty_profile")
    department: Mapped[Department | None] = relationship(back_populates="faculty")
    batch_links: Mapped[list[FacultyBatch]] = relationship(back_populates="faculty", cascade="all, delete-orphan")
    attendance_sessions: Mapped[list[AttendanceSession]] = relationship(back_populates="faculty")

class Student(Base):
    __tablename__ = "students"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    roll_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date_of_birth: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    profile_photo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    user: Mapped[User] = relationship(back_populates="student_profile")
    enrollments: Mapped[list[StudentEnrollment]] = relationship(back_populates="student", cascade="all, delete-orphan")
    contacts: Mapped[list[StudentContact]] = relationship(back_populates="student", cascade="all, delete-orphan")
    address: Mapped[StudentAddress | None] = relationship(back_populates="student", uselist=False, cascade="all, delete-orphan")
    qualifications: Mapped[list[StudentQualification]] = relationship(back_populates="student", cascade="all, delete-orphan")
    face_enrollment: Mapped[FaceEnrollment | None] = relationship(back_populates="student", uselist=False, cascade="all, delete-orphan")
    attendance_records: Mapped[list[AttendanceRecord]] = relationship(back_populates="student")
    recognition_events: Mapped[list[RecognitionEvent]] = relationship(back_populates="student")

class Subject(UUIDPKMixin, Base):
    __tablename__ = "subjects"
    code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    department: Mapped[Department | None] = relationship(back_populates="subjects")
    attendance_sessions: Mapped[list[AttendanceSession]] = relationship(back_populates="subject")

class SystemSettings(UUIDPKMixin, Base):
    __tablename__ = "system_settings"
    recognition_threshold: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.45)
    liveness_threshold: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.85)
    quality_threshold: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.50)
    attendance_cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    camera_resolution: Mapped[str] = mapped_column(String(32), nullable=False, default="1280x720")
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    updated_by_user: Mapped[User | None] = relationship(foreign_keys=[updated_by])

class AttendanceSession(UUIDPKMixin, Base):
    __tablename__ = "attendance_sessions"
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False, index=True)
    faculty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("faculty.user_id", ondelete="RESTRICT"), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[AttendanceSessionStatus] = mapped_column(SAEnum(AttendanceSessionStatus, name="attendance_session_status"), nullable=False, default=AttendanceSessionStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    batch: Mapped[Batch] = relationship(back_populates="attendance_sessions")
    faculty: Mapped[Faculty] = relationship(back_populates="attendance_sessions", foreign_keys=[faculty_id])
    subject: Mapped[Subject | None] = relationship(back_populates="attendance_sessions")
    records: Mapped[list[AttendanceRecord]] = relationship(back_populates="attendance_session", cascade="all, delete-orphan")
    recognition_events: Mapped[list[RecognitionEvent]] = relationship(back_populates="attendance_session", cascade="all, delete-orphan")

class FaceEnrollment(UUIDPKMixin, Base):
    __tablename__ = "face_enrollments"
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.user_id", ondelete="CASCADE"), nullable=False, unique=True)
    status: Mapped[FaceEnrollmentStatus] = mapped_column(SAEnum(FaceEnrollmentStatus, name="face_enrollment_status"), nullable=False, default=FaceEnrollmentStatus.PENDING)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    model_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    samples_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    student: Mapped[Student] = relationship(back_populates="face_enrollment")
    embeddings: Mapped[list[FaceEmbedding]] = relationship(back_populates="enrollment", cascade="all, delete-orphan")

class FacultyBatch(Base):
    __tablename__ = "faculty_batches"
    faculty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("faculty.user_id", ondelete="CASCADE"), primary_key=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("batches.id", ondelete="CASCADE"), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    faculty: Mapped[Faculty] = relationship(back_populates="batch_links")
    batch: Mapped[Batch] = relationship(back_populates="faculty_links")

class RegistrationForm(UUIDPKMixin, Base):
    __tablename__ = "registration_forms"
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, unique=True)
    google_form_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    google_sheet_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    form_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[FormStatus] = mapped_column(SAEnum(FormStatus, name="registration_form_status"), nullable=False, default=FormStatus.ACTIVE)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    field_mapping: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    batch: Mapped[Batch] = relationship(back_populates="registration_form")
    created_by_user: Mapped[User] = relationship(foreign_keys=[created_by])
    submissions: Mapped[list[RegistrationSubmission]] = relationship(back_populates="form", cascade="all, delete-orphan")

class StudentAddress(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "student_addresses"
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.user_id", ondelete="CASCADE"), nullable=False, unique=True)
    address_line: Mapped[str] = mapped_column(String(512), nullable=False)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    student: Mapped[Student] = relationship(back_populates="address")

class StudentContact(UUIDPKMixin, Base):
    __tablename__ = "student_contacts"
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.user_id", ondelete="CASCADE"), nullable=False)
    contact_type: Mapped[ContactType] = mapped_column(SAEnum(ContactType, name="contact_type"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mobile_number: Mapped[str] = mapped_column(String(32), nullable=False)
    relationship_name: Mapped[str | None] = mapped_column(
    "relationship",
    String(64),
    nullable=True,
    )
    student: Mapped[Student] = relationship(back_populates="contacts")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (
    UniqueConstraint(
        "student_id",
        "contact_type",
        name="uq_student_contact_type",
    ),
    Index(
        "ix_student_contacts_student_id",
        "student_id",
    ),
    Index(
        "uq_student_contacts_one_primary",
        "student_id",
        unique=True,
        postgresql_where=text("is_primary = true"),
        sqlite_where=text("is_primary = true"),
    ),
)

class StudentEnrollment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "student_enrollments"
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.user_id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False, index=True)
    semester: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enrollment_status: Mapped[EnrollmentStatus] = mapped_column(SAEnum(EnrollmentStatus, name="enrollment_status"), nullable=False, default=EnrollmentStatus.ACTIVE)
    student: Mapped[Student] = relationship(back_populates="enrollments")
    batch: Mapped[Batch] = relationship(back_populates="enrollments")

class StudentQualification(UUIDPKMixin, Base):
    __tablename__ = "student_qualifications"
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.user_id", ondelete="CASCADE"), nullable=False, index=True)
    qualification_type: Mapped[QualificationType] = mapped_column(SAEnum(QualificationType, name="qualification_type"), nullable=False)
    board: Mapped[str | None] = mapped_column(String(255), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    course: Mapped[str | None] = mapped_column(String(255), nullable=True)
    passing_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    score_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    roll_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    student: Mapped[Student] = relationship(back_populates="qualifications")
    __table_args__ = (UniqueConstraint("student_id", "qualification_type", name="uq_student_qualification_type"),)

class AttendanceRecord(UUIDPKMixin, Base):
    __tablename__ = "attendance_records"
    attendance_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.user_id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[AttendanceStatus] = mapped_column(SAEnum(AttendanceStatus, name="attendance_status"), nullable=False)
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    recognition_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    attendance_session: Mapped[AttendanceSession] = relationship(back_populates="records")
    student: Mapped[Student] = relationship(back_populates="attendance_records")
    __table_args__ = (UniqueConstraint("attendance_session_id", "student_id", name="uq_attendance_once_per_session"),)

class FaceEmbedding(UUIDPKMixin, Base):
    __table_args__ = (
    Index(
        "ix_face_embeddings_embedding_hnsw",
        "embedding",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    __tablename__ = "face_embeddings"
    enrollment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("face_enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(512), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    enrollment: Mapped[FaceEnrollment] = relationship(back_populates="embeddings")

class RecognitionEvent(UUIDPKMixin, Base):
    __tablename__ = "recognition_events"
    attendance_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("students.user_id"), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    recognition_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[RecognitionResult] = mapped_column(SAEnum(RecognitionResult, name="recognition_result"), nullable=False)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    attendance_session: Mapped[AttendanceSession] = relationship(back_populates="recognition_events")
    student: Mapped[Student | None] = relationship(back_populates="recognition_events")

class RegistrationSubmission(UUIDPKMixin, Base):
    __tablename__ = "registration_submissions"
    form_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("registration_forms.id", ondelete="CASCADE"), nullable=False, index=True)
    google_response_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(SAEnum(SubmissionStatus, name="submission_status"), nullable=False, default=SubmissionStatus.PENDING)
    student_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("students.user_id"), nullable=True)
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    form: Mapped[RegistrationForm] = relationship(back_populates="submissions")
    student: Mapped[Student | None] = relationship()

class AccountActivationToken(UUIDPKMixin, Base):
    __tablename__ = "account_activation_tokens"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    user: Mapped[User] = relationship(back_populates="activation_tokens")

class FacultyRegistrationStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class FacultyRegistrationRequest(Base):
    __tablename__ = "faculty_registration_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    employee_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )

    designation: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    status: Mapped[FacultyRegistrationStatus] = mapped_column(
        SAEnum(
            FacultyRegistrationStatus,
            name="faculty_registration_status",
        ),
        nullable=False,
        default=FacultyRegistrationStatus.PENDING,
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    department: Mapped["Department"] = relationship(
        back_populates="faculty_registration_requests",
    )

    reviewer: Mapped["User | None"] = relationship(
        foreign_keys=[reviewed_by],
    )

    __table_args__ = (
    Index(
        "ix_faculty_registration_requests_email",
        "email",
    ),
    Index(
        "ix_faculty_registration_requests_employee_id",
        "employee_id",
    ),
    Index(
        "ix_faculty_registration_requests_status",
        "status",
    ),
    )

class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    token_hash = Column(
        String,
        nullable=False,
        unique=True,
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    used_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )