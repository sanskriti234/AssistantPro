import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    AttendanceRecord,
    AttendanceStatus,
    Batch,
    Department,
    EnrollmentStatus,
    RecognitionEvent,
    RecognitionResult,
    Student,
    StudentEnrollment,
)
from app.services.academic_service import batch_to_dict, _batch_registered_count, _batch_today_attendance_pct


def dashboard_stats(db: Session) -> dict:
    total_students = db.scalar(
        select(func.count(func.distinct(StudentEnrollment.student_id))).where(
            StudentEnrollment.enrollment_status == EnrollmentStatus.ACTIVE
        )
    ) or 0

    from app.database.models import FaceEnrollment, FaceEnrollmentStatus

    face_enrolled = db.scalar(
        select(func.count(func.distinct(FaceEnrollment.student_id))).where(
            FaceEnrollment.status == FaceEnrollmentStatus.COMPLETE
        )
    ) or 0

    batches = list(db.scalars(select(Batch)))
    pct_values = [_batch_today_attendance_pct(db, b.id) for b in batches if _batch_registered_count(db, b.id) > 0]
    avg_attendance = round(sum(pct_values) / len(pct_values), 1) if pct_values else 0.0

    today = datetime.now(timezone.utc).date()
    spoof_attempts = db.scalar(
        select(func.count(RecognitionEvent.id)).where(
            RecognitionEvent.result == RecognitionResult.SPOOF, func.date(RecognitionEvent.occurred_at) == today
        )
    ) or 0

    return {
        "totalStudents": total_students,
        "registeredStudents": total_students,
        "faceEnrolledStudents": face_enrolled,
        "todayAttendancePct": avg_attendance,
        "spoofAttempts": spoof_attempts,
    }


def attendance_trend(db: Session, days: int = 6) -> list[dict]:
    """Institution-wide present/registered percentage for each of the last N days."""
    total_registered = db.scalar(
        select(func.count(func.distinct(StudentEnrollment.student_id))).where(
            StudentEnrollment.enrollment_status == EnrollmentStatus.ACTIVE
        )
    ) or 0

    out = []
    today = datetime.now(timezone.utc).date()
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        present = db.scalar(
            select(func.count(func.distinct(AttendanceRecord.student_id))).where(
                AttendanceRecord.status == AttendanceStatus.PRESENT, func.date(AttendanceRecord.marked_at) == d
            )
        ) or 0
        pct = round((present / total_registered) * 100, 1) if total_registered else 0.0
        out.append({"day": d.strftime("%a"), "pct": pct})
    return out


def department_attendance(db: Session) -> list[dict]:
    departments = list(db.scalars(select(Department)))
    out = []
    for dept in departments:
        batches = list(db.scalars(select(Batch).where(Batch.department_id == dept.id)))
        if not batches:
            continue
        pcts = [_batch_today_attendance_pct(db, b.id) for b in batches if _batch_registered_count(db, b.id) > 0]
        out.append({"department": dept.name, "avgPct": round(sum(pcts) / len(pcts), 1) if pcts else 0.0})
    return out


def batch_attendance(db: Session, batch_ids: list[uuid.UUID] | None = None) -> list[dict]:
    stmt = select(Batch)
    if batch_ids:
        stmt = stmt.where(Batch.id.in_(batch_ids))
    batches = list(db.scalars(stmt))
    return [{"name": b.name, "pct": _batch_today_attendance_pct(db, b.id)} for b in batches]


def recognition_success_pct(db: Session) -> float:
    total = db.scalar(select(func.count(RecognitionEvent.id))) or 0
    if total == 0:
        return 0.0
    verified = db.scalar(select(func.count(RecognitionEvent.id)).where(RecognitionEvent.result == RecognitionResult.VERIFIED)) or 0
    return round((verified / total) * 100, 1)


def spoof_attempts_total(db: Session) -> int:
    return db.scalar(select(func.count(RecognitionEvent.id)).where(RecognitionEvent.result == RecognitionResult.SPOOF)) or 0
