import time
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.base import utcnow
from app.database.models import (
    AttendanceRecord,
    AttendanceSession,
    AttendanceSessionStatus,
    AttendanceStatus,
    EnrollmentStatus,
    FaceEmbedding,
    FaceEnrollment,
    FaceEnrollmentStatus,
    FacultyBatch,
    RecognitionEvent,
    RecognitionResult,
    Student,
    StudentEnrollment,
    Subject,
    SystemSettings,
)
from app.services import face_pipeline_service
from app.services.audit import log_action
from app.services.face_pipeline_service import FrameOutcome, PipelineUnavailable


def get_or_create_subject(db: Session, name: str) -> Subject:
    subject = db.query(Subject).filter(Subject.name == name).first()
    if subject:
        return subject
    subject = Subject(name=name)
    db.add(subject)
    db.flush()
    return subject


def assert_faculty_assigned(db: Session, faculty_id: uuid.UUID, batch_id: uuid.UUID) -> None:
    link = db.query(FacultyBatch).filter(FacultyBatch.faculty_id == faculty_id, FacultyBatch.batch_id == batch_id).first()
    if link is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not assigned to this batch")


def start_session(db: Session, faculty_id: uuid.UUID, batch_id: uuid.UUID, subject_name: str) -> AttendanceSession:
    assert_faculty_assigned(db, faculty_id, batch_id)
    subject = get_or_create_subject(db, subject_name)
    session = AttendanceSession(
        batch_id=batch_id,
        faculty_id=faculty_id,
        subject_id=subject.id,
        status=AttendanceSessionStatus.ACTIVE,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    log_action(db, user_id=faculty_id, action="FACULTY_STARTED_ATTENDANCE", entity_type="attendance_session", entity_id=str(session.id))
    db.commit()
    return session


def end_session(db: Session, session_id: uuid.UUID, faculty_id: uuid.UUID) -> AttendanceSession:
    session = db.get(AttendanceSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if session.faculty_id != faculty_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your session")
    session.status = AttendanceSessionStatus.COMPLETED
    session.ended_at = utcnow()
    db.commit()
    return session


def session_to_dict(db: Session, session: AttendanceSession) -> dict:
    batch = session.batch
    total = db.scalar(
        select(func.count(StudentEnrollment.id)).where(
            StudentEnrollment.batch_id == batch.id, StudentEnrollment.enrollment_status == EnrollmentStatus.ACTIVE
        )
    ) or 0
    present = db.scalar(
        select(func.count(AttendanceRecord.id)).where(
            AttendanceRecord.attendance_session_id == session.id, AttendanceRecord.status == AttendanceStatus.PRESENT
        )
    ) or 0
    return {
        "id": str(session.id),
        "batchId": str(batch.id),
        "batchName": batch.name,
        "section": batch.section,
        "subject": session.subject.name if session.subject else "",
        "facultyId": str(session.faculty_id),
        "startedAt": session.started_at.isoformat(),
        "present": present,
        "absent": max(total - present, 0),
        "total": total,
        "active": session.status == AttendanceSessionStatus.ACTIVE,
    }


_OUTCOME_TO_RESULT = {
    FrameOutcome.NO_FACE: RecognitionResult.POOR_QUALITY,
    FrameOutcome.LOW_QUALITY: RecognitionResult.POOR_QUALITY,
    FrameOutcome.MULTIPLE_FACES: RecognitionResult.MULTIPLE_FACES,
    FrameOutcome.SPOOF_DETECTED: RecognitionResult.SPOOF,
}


def _find_nearest_enrolled_student(db: Session, batch_id: uuid.UUID, query_embedding) -> tuple[Student, float] | None:
    """
    pgvector cosine-distance nearest-neighbor search, scoped to students
    actively enrolled in this batch with a COMPLETE face enrollment. A
    student may have several stored embeddings (one per valid enrollment
    sample) - this naturally finds the single closest sample across every
    enrolled student, which is the correct nearest-neighbor match.
    """
    distance_col = FaceEmbedding.embedding.cosine_distance(query_embedding).label("distance")
    row = (
        db.query(FaceEmbedding, distance_col)
        .join(FaceEnrollment, FaceEmbedding.enrollment_id == FaceEnrollment.id)
        .join(Student, FaceEnrollment.student_id == Student.user_id)
        .join(StudentEnrollment, StudentEnrollment.student_id == Student.user_id)
        .filter(
            StudentEnrollment.batch_id == batch_id,
            StudentEnrollment.enrollment_status == EnrollmentStatus.ACTIVE,
            FaceEnrollment.status == FaceEnrollmentStatus.COMPLETE,
        )
        .order_by(distance_col)
        .first()
    )
    if row is None:
        return None
    embedding_row, distance = row
    similarity = 1.0 - float(distance)
    return embedding_row.enrollment.student, similarity


def submit_frame(db: Session, session_id: uuid.UUID, frame_data_url: str) -> dict:
    """
    The backend-owned attendance decision engine - real inference (see
    app/services/face_pipeline_service.py), no simulated/random results.

    Pipeline: SCRFD detection -> MiniFASNetV2 liveness -> ArcFace/AdaFace-slot
    embedding -> pgvector cosine-similarity match against this batch's
    enrolled students -> decision. The frontend never computes this decision;
    it only renders whatever this function returns. Persists a
    RecognitionEvent for every attempt and only ever creates ONE
    AttendanceRecord per (session, student) - enforced additionally at the
    database level by uq_attendance_once_per_session, so even a buggy caller
    (or a race between two near-simultaneous frames) can't double-mark.

    Raises PipelineUnavailable (unchanged from the caller's perspective if
    models aren't loaded) - the route surfaces this as 503. This function
    never fabricates a recognition result when the models aren't ready
    (Step 9).
    """
    session = db.get(AttendanceSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if session.status != AttendanceSessionStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Session is not active")
    if not frame_data_url or "," not in frame_data_url:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid frame payload")

    settings = get_settings()
    start = time.monotonic()

    image = face_pipeline_service.decode_image(frame_data_url)
    analysis = face_pipeline_service.analyze_frame(image, check_liveness=True)

    result: RecognitionResult
    student: Student | None = None
    recognition_score = liveness_score = quality_score = None

    if analysis.outcome in _OUTCOME_TO_RESULT:
        result = _OUTCOME_TO_RESULT[analysis.outcome]
        if analysis.detection_score is not None:
            quality_score = round(analysis.detection_score * 100, 1)
        if analysis.liveness_score is not None:
            liveness_score = round(analysis.liveness_score * 100, 1)
    else:
        # OK: a single, live, good-quality face with a real embedding - now match identity.
        quality_score = round(analysis.detection_score * 100, 1) if analysis.detection_score is not None else None
        liveness_score = round(analysis.liveness_score * 100, 1) if analysis.liveness_score is not None else None

        match = _find_nearest_enrolled_student(db, session.batch_id, analysis.embedding.tolist())
        if match is None:
            result = RecognitionResult.UNKNOWN
        else:
            candidate, similarity = match
            recognition_score = round(similarity * 100, 1)

            if similarity < settings.face_similarity_threshold:
                result = RecognitionResult.UNKNOWN
            else:
                student = candidate
                already = db.query(AttendanceRecord).filter(
                    AttendanceRecord.attendance_session_id == session.id,
                    AttendanceRecord.student_id == student.user_id,
                ).first()
                result = RecognitionResult.ALREADY_MARKED if already else RecognitionResult.VERIFIED

    processing_ms = int((time.monotonic() - start) * 1000)

    db.add(RecognitionEvent(
        attendance_session_id=session.id,
        student_id=student.user_id if student else None,
        recognition_score=recognition_score,
        liveness_score=liveness_score,
        quality_score=quality_score,
        result=result,
        processing_time_ms=processing_ms,
        model_version="scrfd+arcface+minifasnetv2",
    ))

    marked_at_out = None
    if result == RecognitionResult.VERIFIED and student:
        record = AttendanceRecord(
            attendance_session_id=session.id,
            student_id=student.user_id,
            status=AttendanceStatus.PRESENT,
            recognition_score=recognition_score,
            liveness_score=liveness_score,
            quality_score=quality_score,
        )
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            # Two near-simultaneous frames matched the same student - the
            # database's uq_attendance_once_per_session constraint is the
            # real backstop here, not application logic.
            db.rollback()
            result = RecognitionResult.ALREADY_MARKED
        else:
            log_action(
                db, user_id=session.faculty_id, action="ATTENDANCE_MARKED",
                entity_type="attendance_record", entity_id=str(record.id),
            )
            db.commit()
            marked_at_out = record.marked_at.strftime("%I:%M %p")
    elif result == RecognitionResult.SPOOF:
        log_action(db, user_id=session.faculty_id, action="SPOOF_DETECTED", entity_type="attendance_session", entity_id=str(session.id))
        db.commit()
    else:
        db.commit()

    if result == RecognitionResult.ALREADY_MARKED and student:
        prior = db.query(AttendanceRecord).filter(
            AttendanceRecord.attendance_session_id == session.id, AttendanceRecord.student_id == student.user_id
        ).first()
        marked_at_out = prior.marked_at.strftime("%I:%M %p") if prior else None

    return {
        "status": result.value.lower(),
        "studentName": student.full_name if student else None,
        "rollNumber": student.roll_number if student else None,
        "recognitionScore": recognition_score,
        "livenessScore": liveness_score,
        "markedAt": marked_at_out,
    }


def record_to_dict(record: AttendanceRecord) -> dict:
    session = record.session
    return {
        "id": str(record.id),
        "studentId": str(record.student_id),
        "studentName": record.student.full_name,
        "rollNumber": record.student.roll_number,
        "batchId": str(session.batch_id),
        "subject": session.subject.name if session.subject else "",
        "date": record.marked_at.date().isoformat(),
        "time": record.marked_at.strftime("%I:%M %p"),
        "recognitionScore": record.recognition_score or 0,
        "livenessScore": record.liveness_score or 0,
        "status": record.status.value.lower(),
    }


def attendance_history(
    db: Session,
    *,
    batch_id: uuid.UUID | None = None,
    date_str: str | None = None,
    subject_name: str | None = None,
    student_id: uuid.UUID | None = None,
) -> list[dict]:
    """
    Faculty/admin history view: only sessions that actually produced a
    PRESENT record are meaningful rows here (absent students simply have no
    record for that session). student_attendance_history below fills in the
    implied ABSENT rows for a single student's own history page.
    """
    q = db.query(AttendanceRecord).join(AttendanceSession)
    if batch_id:
        q = q.filter(AttendanceSession.batch_id == batch_id)
    if date_str:
        q = q.filter(func.date(AttendanceRecord.marked_at) == date_str)
    if subject_name:
        q = q.join(Subject).filter(Subject.name == subject_name)
    if student_id:
        q = q.filter(AttendanceRecord.student_id == student_id)
    records = q.order_by(AttendanceRecord.marked_at.desc()).all()
    return [record_to_dict(r) for r in records]


def student_attendance_history(db: Session, student_id: uuid.UUID) -> list[dict]:
    """
    Builds the student's own attendance list, including implied ABSENT rows
    for sessions of their batch where no PRESENT record exists for them.
    """
    enrollment = (
        db.query(StudentEnrollment)
        .filter(StudentEnrollment.student_id == student_id, StudentEnrollment.enrollment_status == EnrollmentStatus.ACTIVE)
        .first()
    )
    if enrollment is None:
        return []

    sessions = (
        db.query(AttendanceSession)
        .filter(AttendanceSession.batch_id == enrollment.batch_id, AttendanceSession.status != AttendanceSessionStatus.CANCELLED)
        .order_by(AttendanceSession.started_at.desc())
        .all()
    )
    present_by_session = {
        r.attendance_session_id: r
        for r in db.query(AttendanceRecord).filter(AttendanceRecord.student_id == student_id).all()
    }

    out = []
    for s in sessions:
        record = present_by_session.get(s.id)
        if record:
            out.append(record_to_dict(record))
        else:
            out.append({
                "id": f"absent-{s.id}",
                "studentId": str(student_id),
                "studentName": enrollment.student.full_name,
                "rollNumber": enrollment.student.roll_number,
                "batchId": str(s.batch_id),
                "subject": s.subject.name if s.subject else "",
                "date": s.started_at.date().isoformat(),
                "time": "",
                "recognitionScore": 0,
                "livenessScore": 0,
                "status": "absent",
            })
    return out
