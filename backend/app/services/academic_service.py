import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    AcademicSession,
    AttendanceRecord,
    AttendanceStatus,
    Batch,
    Course,
    Department,
    EnrollmentStatus,
    FaceEnrollment,
    FaceEnrollmentStatus,
    FormStatus,
    RegistrationForm,
    RegistrationSubmission,
    SessionStatus,
    Student,
    StudentEnrollment,
    SubmissionStatus,
)


def _batch_registered_count(db: Session, batch_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count(StudentEnrollment.id)).where(
            StudentEnrollment.batch_id == batch_id,
            StudentEnrollment.enrollment_status == EnrollmentStatus.ACTIVE,
        )
    ) or 0


def _batch_face_enrolled_count(db: Session, batch_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count(func.distinct(Student.user_id)))
        .select_from(Student)
        .join(StudentEnrollment, StudentEnrollment.student_id == Student.user_id)
        .join(FaceEnrollment, FaceEnrollment.student_id == Student.user_id)
        .where(
            StudentEnrollment.batch_id == batch_id,
            StudentEnrollment.enrollment_status == EnrollmentStatus.ACTIVE,
            FaceEnrollment.status == FaceEnrollmentStatus.COMPLETE,
        )
    ) or 0


def _batch_today_attendance_pct(db: Session, batch_id: uuid.UUID) -> float:
    registered = _batch_registered_count(db, batch_id)
    if registered == 0:
        return 0.0
    today = datetime.now(timezone.utc).date()
    present = db.scalar(
        select(func.count(func.distinct(AttendanceRecord.student_id)))
        .join(StudentEnrollment, StudentEnrollment.student_id == AttendanceRecord.student_id)
        .where(
            StudentEnrollment.batch_id == batch_id,
            AttendanceRecord.status == AttendanceStatus.PRESENT,
            func.date(AttendanceRecord.marked_at) == today,
        )
    ) or 0
    return round((present / registered) * 100, 1)


def batch_to_dict(db: Session, batch: Batch) -> dict:
    registered = _batch_registered_count(db, batch.id)
    enrolled = _batch_face_enrolled_count(db, batch.id)
    form = batch.registration_form
    responses = synced = pending = 0
    if form:
        responses = db.scalar(select(func.count(RegistrationSubmission.id)).where(RegistrationSubmission.form_id == form.id)) or 0
        synced = db.scalar(
            select(func.count(RegistrationSubmission.id)).where(
                RegistrationSubmission.form_id == form.id, RegistrationSubmission.status == SubmissionStatus.SYNCED
            )
        ) or 0
        pending = db.scalar(
            select(func.count(RegistrationSubmission.id)).where(
                RegistrationSubmission.form_id == form.id, RegistrationSubmission.status == SubmissionStatus.PENDING
            )
        ) or 0

    return {
        "id": str(batch.id),
        "name": batch.name,
        "department": batch.department.name,
        "year": batch.year,
        "section": batch.section,
        "sessionId": str(batch.academic_session_id),
        "registeredStudents": registered,
        "faceEnrolled": enrolled,
        "pendingEnrollment": max(registered - enrolled, 0),
        "todayAttendancePct": _batch_today_attendance_pct(db, batch.id),
        "formStatus": (form.status.value.lower() if form else "inactive"),
        "formResponses": responses,
        "formSynced": synced,
        "formPending": pending,
        "formUrl": form.form_url if form else None,
        "googleFormId": form.google_form_id if form else None,
        "formCreatedAt": form.created_at.isoformat() if form else None,
        "registrationFormId": str(form.id) if form else None,
        "formLastSyncedAt": form.last_synced_at.isoformat() if form and form.last_synced_at else None,
    }


def session_to_dict(db: Session, session: AcademicSession) -> dict:
    batch_ids = [str(b.id) for b in db.scalars(select(Batch).where(Batch.academic_session_id == session.id))]
    return {
        "id": str(session.id),
        "label": session.name,
        "active": session.status == SessionStatus.ACTIVE,
        "batchIds": batch_ids,
    }


def list_sessions(db: Session) -> list[dict]:
    sessions = db.scalars(select(AcademicSession).order_by(AcademicSession.created_at.desc())).all()
    return [session_to_dict(db, s) for s in sessions]


def toggle_session(db: Session, session_id: uuid.UUID) -> AcademicSession | None:
    session = db.get(AcademicSession, session_id)
    if session is None:
        return None
    session.status = SessionStatus.INACTIVE if session.status == SessionStatus.ACTIVE else SessionStatus.ACTIVE
    db.commit()
    db.refresh(session)
    return session


def create_session(db: Session, label: str) -> AcademicSession:
    session = AcademicSession(name=label, status=SessionStatus.ACTIVE)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_batches(db: Session, session_id: uuid.UUID | None = None) -> list[Batch]:
    stmt = select(Batch)
    if session_id:
        stmt = stmt.where(Batch.academic_session_id == session_id)
    return list(db.scalars(stmt))


def get_or_create_department(db: Session, name: str) -> Department:
    dept = db.query(Department).filter(Department.name == name).first()
    if dept:
        return dept
    code = "".join(w[0] for w in name.split()).upper()[:8] or name[:8].upper()
    base_code, n = code, 1
    while db.query(Department).filter(Department.code == code).first():
        n += 1
        code = f"{base_code}{n}"
    dept = Department(code=code, name=name)
    db.add(dept)
    db.flush()
    return dept


def get_or_create_course(db: Session, name: str, duration_years: int = 4) -> Course:
    course = db.query(Course).filter(Course.name == name).first()
    if course:
        return course
    code = "".join(w[0] for w in name.split()).upper()[:8] or name[:8].upper()
    base_code, n = code, 1
    while db.query(Course).filter(Course.code == code).first():
        n += 1
        code = f"{base_code}{n}"
    course = Course(code=code, name=name, duration_years=duration_years)
    db.add(course)
    db.flush()
    return course


def create_batch(db: Session, *, name: str, department_name: str, year: int, section: str, session_id: uuid.UUID) -> Batch:
    department = get_or_create_department(db, department_name)
    # NOTE: the existing frontend only collects a batch "name" (e.g. "CSE
    # AIML 2027"), not a separate course. We find-or-create a Course keyed
    # on that same name so the schema stays normalized without adding a
    # course-selection field the UI never had. See README limitations.
    course = get_or_create_course(db, name)
    batch = Batch(
        academic_session_id=session_id,
        course_id=course.id,
        department_id=department.id,
        year=year,
        section=section,
        name=name,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def overall_attendance_pct(db: Session, student_id: uuid.UUID) -> float:
    from app.database.models import AttendanceSession

    total_sessions = db.scalar(
        select(func.count(func.distinct(AttendanceSession.id)))
        .join(StudentEnrollment, StudentEnrollment.batch_id == AttendanceSession.batch_id)
        .where(
            StudentEnrollment.student_id == student_id,
            StudentEnrollment.enrollment_status == EnrollmentStatus.ACTIVE,
        )
    ) or 0
    if total_sessions == 0:
        return 0.0
    present = db.scalar(
        select(func.count(AttendanceRecord.id)).where(
            AttendanceRecord.student_id == student_id, AttendanceRecord.status == AttendanceStatus.PRESENT
        )
    ) or 0
    return round((present / total_sessions) * 100, 1)


def batch_students(db: Session, batch_id: uuid.UUID) -> list[dict]:
    enrollments = db.scalars(
        select(StudentEnrollment).where(
            StudentEnrollment.batch_id == batch_id,
            StudentEnrollment.enrollment_status == EnrollmentStatus.ACTIVE,
        )
    )
    out = []
    for e in enrollments:
        student = e.student
        batch = e.batch
        fe = student.face_enrollment
        out.append({
            "id": str(student.user_id),
            "name": student.full_name,
            "rollNumber": student.roll_number,
            "department": batch.department.name,
            "batchId": str(batch.id),
            "section": batch.section,
            "email": student.user.email,
            "phone": next((c.mobile_number for c in student.contacts if c.contact_type.value == "STUDENT"), ""),
            "faceEnrolled": bool(fe and fe.status == FaceEnrollmentStatus.COMPLETE),
            "overallAttendancePct": overall_attendance_pct(db, student.user_id),
        })
    return out
