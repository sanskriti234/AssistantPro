"""
Service-layer tests for the real-pipeline wiring in enrollment_service.py
and attendance_service.py, with face_pipeline_service.analyze_frame mocked
(fast, deterministic, no model files needed - the ML layer itself is
covered separately and only when real weights are present, in
test_ml_pipeline_real.py).
"""

import uuid
from unittest.mock import patch

import numpy as np
import pytest

from app.core.security import hash_password
from app.database.models import (
    AttendanceSession, AttendanceSessionStatus, Faculty, FaceEmbedding, FaceEnrollment,
    FaceEnrollmentStatus, FacultyBatch, Role, Student, StudentEnrollment,
    EnrollmentStatus, User,
)
from app.services import attendance_service, enrollment_service, face_pipeline_service
from app.services.face_pipeline_service import FrameAnalysis, FrameOutcome, PipelineUnavailable
from tests.test_auth_and_constraints import _make_academic_scaffold


def _fake_embedding(seed: int) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return rng.randn(512).astype(np.float32)


# --- Enrollment ---------------------------------------------------------

def test_validate_sample_accepts_good_frame_and_buffers_embedding(db_session):
    embedding = _fake_embedding(1)
    analysis = FrameAnalysis(outcome=FrameOutcome.OK, detection_score=0.9, liveness_score=0.95, embedding=embedding)
    student_id = uuid.uuid4()

    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", return_value=analysis):
        accepted, reason = enrollment_service.validate_sample("data:image/jpeg;base64,Zm9v", student_id)

    assert accepted is True
    assert reason is None
    assert len(enrollment_service._pending_embeddings[student_id]) == 1
    enrollment_service._consume_pending_embeddings(student_id)  # cleanup


def test_validate_sample_rejects_no_face(db_session):
    analysis = FrameAnalysis(outcome=FrameOutcome.NO_FACE)
    student_id = uuid.uuid4()
    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", return_value=analysis):
        accepted, reason = enrollment_service.validate_sample("data:image/jpeg;base64,Zm9v", student_id)
    assert accepted is False
    assert "face" in reason.lower()


def test_validate_sample_rejects_multiple_faces(db_session):
    analysis = FrameAnalysis(outcome=FrameOutcome.MULTIPLE_FACES)
    student_id = uuid.uuid4()
    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", return_value=analysis):
        accepted, reason = enrollment_service.validate_sample("data:image/jpeg;base64,Zm9v", student_id)
    assert accepted is False
    assert "multiple" in reason.lower()


def test_validate_sample_invalid_payload_rejected_without_calling_pipeline(db_session):
    student_id = uuid.uuid4()
    with patch.object(face_pipeline_service, "analyze_frame") as mock_analyze:
        accepted, reason = enrollment_service.validate_sample("not-a-data-url", student_id)
    assert accepted is False
    mock_analyze.assert_not_called()


def test_validate_sample_propagates_pipeline_unavailable(db_session):
    student_id = uuid.uuid4()
    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", side_effect=PipelineUnavailable("models not loaded")):
        with pytest.raises(PipelineUnavailable):
            enrollment_service.validate_sample("data:image/jpeg;base64,Zm9v", student_id)


def test_finalize_enrollment_succeeds_with_enough_buffered_samples(db_session):
    user = User(email=f"enroll-{uuid.uuid4().hex[:8]}@coresight.edu", password_hash=hash_password("x"), role=Role.STUDENT)
    db_session.add(user)
    db_session.flush()
    student = Student(user_id=user.id, roll_number=f"ENR-{uuid.uuid4().hex[:8]}", full_name="Enroll Test")
    db_session.add(student)
    db_session.commit()

    with enrollment_service._buffer_lock:
        enrollment_service._pending_embeddings[student.user_id] = [_fake_embedding(i) for i in range(15)]

    result = enrollment_service.finalize_enrollment(db_session, student.user_id, 15, [])

    assert result["status"] == "complete"
    assert result["validSamples"] == 15

    fe = db_session.query(FaceEnrollment).filter(FaceEnrollment.student_id == student.user_id).first()
    assert fe.status == FaceEnrollmentStatus.COMPLETE
    embeddings = db_session.query(FaceEmbedding).filter(FaceEmbedding.enrollment_id == fe.id).all()
    assert len(embeddings) == 15


def test_finalize_enrollment_fails_with_insufficient_samples(db_session):
    user = User(email=f"enroll2-{uuid.uuid4().hex[:8]}@coresight.edu", password_hash=hash_password("x"), role=Role.STUDENT)
    db_session.add(user)
    db_session.flush()
    student = Student(user_id=user.id, roll_number=f"ENR2-{uuid.uuid4().hex[:8]}", full_name="Enroll Test 2")
    db_session.add(student)
    db_session.commit()

    with enrollment_service._buffer_lock:
        enrollment_service._pending_embeddings[student.user_id] = [_fake_embedding(i) for i in range(3)]

    result = enrollment_service.finalize_enrollment(db_session, student.user_id, 3, [])

    assert result["status"] == "failed"
    assert result["validSamples"] == 3
    fe = db_session.query(FaceEnrollment).filter(FaceEnrollment.student_id == student.user_id).first()
    assert fe.status == FaceEnrollmentStatus.FAILED


def test_finalize_enrollment_ignores_client_supplied_embeddings(db_session):
    """The server never trusts client-supplied embeddings - only its own buffered ones from real inference."""
    user = User(email=f"enroll3-{uuid.uuid4().hex[:8]}@coresight.edu", password_hash=hash_password("x"), role=Role.STUDENT)
    db_session.add(user)
    db_session.flush()
    student = Student(user_id=user.id, roll_number=f"ENR3-{uuid.uuid4().hex[:8]}", full_name="Enroll Test 3")
    db_session.add(student)
    db_session.commit()

    fake_client_embeddings = [[9.9] * 512 for _ in range(20)]  # attacker-supplied nonsense
    result = enrollment_service.finalize_enrollment(db_session, student.user_id, 20, fake_client_embeddings)

    # No real embeddings were buffered server-side, so this fails despite the client claiming 20 valid samples.
    assert result["status"] == "failed"
    assert result["validSamples"] == 0


def test_reenrollment_replaces_previous_embeddings(db_session):
    user = User(email=f"enroll4-{uuid.uuid4().hex[:8]}@coresight.edu", password_hash=hash_password("x"), role=Role.STUDENT)
    db_session.add(user)
    db_session.flush()
    student = Student(user_id=user.id, roll_number=f"ENR4-{uuid.uuid4().hex[:8]}", full_name="Enroll Test 4")
    db_session.add(student)
    db_session.commit()

    with enrollment_service._buffer_lock:
        enrollment_service._pending_embeddings[student.user_id] = [_fake_embedding(i) for i in range(15)]
    enrollment_service.finalize_enrollment(db_session, student.user_id, 15, [])

    with enrollment_service._buffer_lock:
        enrollment_service._pending_embeddings[student.user_id] = [_fake_embedding(i + 100) for i in range(18)]
    enrollment_service.finalize_enrollment(db_session, student.user_id, 18, [])

    fe = db_session.query(FaceEnrollment).filter(FaceEnrollment.student_id == student.user_id).first()
    embeddings = db_session.query(FaceEmbedding).filter(FaceEmbedding.enrollment_id == fe.id).all()
    assert len(embeddings) == 18  # not 33 - old embeddings were replaced, not accumulated


# --- Attendance ----------------------------------------------------------

def _make_attendance_scaffold(db_session):
    batch = _make_academic_scaffold(db_session)
    fac_user = User(email=f"fac-ml-{uuid.uuid4().hex[:8]}@coresight.edu", password_hash=hash_password("x"), role=Role.FACULTY)
    db_session.add(fac_user)
    db_session.flush()
    faculty = Faculty(user_id=fac_user.id, employee_id=f"EMP-ML-{uuid.uuid4().hex[:8]}", name="ML Test Faculty")
    db_session.add(faculty)
    db_session.add(FacultyBatch(faculty_id=faculty.user_id, batch_id=batch.id))
    db_session.commit()

    session = AttendanceSession(batch_id=batch.id, faculty_id=faculty.user_id, status=AttendanceSessionStatus.ACTIVE)
    db_session.add(session)
    db_session.commit()
    return batch, faculty, session


def _enroll_student(db_session, batch, embedding: np.ndarray, roll_suffix: str):
    user = User(email=f"stu-ml-{roll_suffix}@coresight.edu", password_hash=hash_password("x"), role=Role.STUDENT)
    db_session.add(user)
    db_session.flush()
    student = Student(user_id=user.id, roll_number=f"ML-{roll_suffix}", full_name=f"ML Student {roll_suffix}")
    db_session.add(student)
    db_session.flush()
    db_session.add(StudentEnrollment(student_id=student.user_id, batch_id=batch.id, enrollment_status=EnrollmentStatus.ACTIVE))
    fe = FaceEnrollment(student_id=student.user_id, status=FaceEnrollmentStatus.COMPLETE)
    db_session.add(fe)
    db_session.flush()
    db_session.add(FaceEmbedding(enrollment_id=fe.id, embedding=embedding.tolist(), quality_score=90.0, model_name="test"))
    db_session.commit()
    return student


def test_submit_frame_verified_when_embedding_matches_enrolled_student(db_session):
    batch, faculty, session = _make_attendance_scaffold(db_session)
    embedding = _fake_embedding(42)
    student = _enroll_student(db_session, batch, embedding, uuid.uuid4().hex[:6])

    analysis = FrameAnalysis(outcome=FrameOutcome.OK, detection_score=0.9, liveness_score=0.95, embedding=embedding)
    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", return_value=analysis):
        result = attendance_service.submit_frame(db_session, session.id, "data:image/jpeg;base64,Zm9v")

    assert result["status"] == "verified"
    assert result["studentName"] == student.full_name


def test_submit_frame_unknown_when_no_enrolled_students_in_batch(db_session):
    batch, faculty, session = _make_attendance_scaffold(db_session)
    analysis = FrameAnalysis(outcome=FrameOutcome.OK, detection_score=0.9, liveness_score=0.95, embedding=_fake_embedding(1))
    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", return_value=analysis):
        result = attendance_service.submit_frame(db_session, session.id, "data:image/jpeg;base64,Zm9v")
    assert result["status"] == "unknown"


def test_submit_frame_unknown_when_similarity_below_threshold(db_session):
    batch, faculty, session = _make_attendance_scaffold(db_session)
    _enroll_student(db_session, batch, _fake_embedding(1), uuid.uuid4().hex[:6])

    different_embedding = _fake_embedding(999)
    analysis = FrameAnalysis(outcome=FrameOutcome.OK, detection_score=0.9, liveness_score=0.95, embedding=different_embedding)
    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", return_value=analysis):
        result = attendance_service.submit_frame(db_session, session.id, "data:image/jpeg;base64,Zm9v")
    assert result["status"] == "unknown"


def test_submit_frame_multiple_enrolled_students_matches_correct_one(db_session):
    batch, faculty, session = _make_attendance_scaffold(db_session)
    embedding_a = _fake_embedding(10)
    embedding_b = _fake_embedding(20)
    embedding_c = _fake_embedding(30)
    student_a = _enroll_student(db_session, batch, embedding_a, uuid.uuid4().hex[:6])
    _enroll_student(db_session, batch, embedding_b, uuid.uuid4().hex[:6])
    _enroll_student(db_session, batch, embedding_c, uuid.uuid4().hex[:6])

    analysis = FrameAnalysis(outcome=FrameOutcome.OK, detection_score=0.9, liveness_score=0.95, embedding=embedding_a)
    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", return_value=analysis):
        result = attendance_service.submit_frame(db_session, session.id, "data:image/jpeg;base64,Zm9v")

    assert result["status"] == "verified"
    assert result["studentName"] == student_a.full_name


def test_submit_frame_spoof_rejects_attendance(db_session):
    batch, faculty, session = _make_attendance_scaffold(db_session)
    _enroll_student(db_session, batch, _fake_embedding(1), uuid.uuid4().hex[:6])

    analysis = FrameAnalysis(outcome=FrameOutcome.SPOOF_DETECTED, detection_score=0.9, liveness_score=0.1, liveness_threshold=0.85)
    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", return_value=analysis):
        result = attendance_service.submit_frame(db_session, session.id, "data:image/jpeg;base64,Zm9v")

    assert result["status"] == "spoof"
    assert result["studentName"] is None

    from app.database.models import AttendanceRecord
    assert db_session.query(AttendanceRecord).filter(AttendanceRecord.attendance_session_id == session.id).count() == 0


def test_submit_frame_no_face_maps_to_poor_quality(db_session):
    batch, faculty, session = _make_attendance_scaffold(db_session)
    analysis = FrameAnalysis(outcome=FrameOutcome.NO_FACE)
    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", return_value=analysis):
        result = attendance_service.submit_frame(db_session, session.id, "data:image/jpeg;base64,Zm9v")
    assert result["status"] == "poor_quality"


def test_submit_frame_multiple_faces(db_session):
    batch, faculty, session = _make_attendance_scaffold(db_session)
    analysis = FrameAnalysis(outcome=FrameOutcome.MULTIPLE_FACES)
    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", return_value=analysis):
        result = attendance_service.submit_frame(db_session, session.id, "data:image/jpeg;base64,Zm9v")
    assert result["status"] == "multiple_faces"


def test_submit_frame_already_marked_on_second_verified_frame(db_session):
    batch, faculty, session = _make_attendance_scaffold(db_session)
    embedding = _fake_embedding(5)
    _enroll_student(db_session, batch, embedding, uuid.uuid4().hex[:6])

    analysis = FrameAnalysis(outcome=FrameOutcome.OK, detection_score=0.9, liveness_score=0.95, embedding=embedding)
    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", return_value=analysis):
        first = attendance_service.submit_frame(db_session, session.id, "data:image/jpeg;base64,Zm9v")
        second = attendance_service.submit_frame(db_session, session.id, "data:image/jpeg;base64,Zm9v")

    assert first["status"] == "verified"
    assert second["status"] == "already_marked"

    from app.database.models import AttendanceRecord
    count = db_session.query(AttendanceRecord).filter(AttendanceRecord.attendance_session_id == session.id).count()
    assert count == 1  # duplicate prevented, not a second record


def test_submit_frame_propagates_pipeline_unavailable(db_session):
    batch, faculty, session = _make_attendance_scaffold(db_session)
    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", side_effect=PipelineUnavailable("models not loaded")):
        with pytest.raises(PipelineUnavailable):
            attendance_service.submit_frame(db_session, session.id, "data:image/jpeg;base64,Zm9v")


def test_submit_frame_via_api_returns_503_when_pipeline_unavailable(client, db_session, make_user):
    batch, faculty, session = _make_attendance_scaffold(db_session)
    token_resp = client.post("/api/auth/login", json={"email": faculty.user.email, "password": "x"})
    assert token_resp.status_code == 200
    token = token_resp.json()["accessToken"]

    with patch.object(face_pipeline_service, "decode_image", return_value=np.zeros((10, 10, 3))), \
         patch.object(face_pipeline_service, "analyze_frame", side_effect=PipelineUnavailable("models not loaded")):
        resp = client.post(
            "/api/attendance/frame",
            json={"sessionId": str(session.id), "frame": "data:image/jpeg;base64,Zm9v"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 503
