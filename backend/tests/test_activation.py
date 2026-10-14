import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.core.security import hash_password, verify_password
from app.database.base import utcnow
from app.database.models import (
    AcademicSession, AccountActivationToken, Batch, Course, Department, FormStatus,
    RegistrationForm, Role, SessionStatus, Student, SubmissionStatus, User,
)
from app.services import activation_service, registration_sync


def _make_form(db_session):
    suffix = uuid.uuid4().hex[:8]
    dept = Department(code=f"AC{suffix}", name=f"Activation Dept {suffix}")
    course = Course(code=f"ACC{suffix}", name=f"Activation Course {suffix}", duration_years=4)
    db_session.add_all([dept, course])
    db_session.flush()
    session = AcademicSession(name=f"act-{suffix}", status=SessionStatus.ACTIVE)
    db_session.add(session)
    db_session.flush()
    batch = Batch(academic_session_id=session.id, course_id=course.id, department_id=dept.id, year=1, section="A", name=f"Activation Batch {suffix}")
    db_session.add(batch)
    db_session.flush()
    admin = User(email=f"act-admin-{suffix}@coresight.edu", password_hash=hash_password("x"), role=Role.ADMIN)
    db_session.add(admin)
    db_session.flush()
    form = RegistrationForm(batch_id=batch.id, google_form_id=f"gform-{suffix}", status=FormStatus.ACTIVE, created_by=admin.id)
    db_session.add(form)
    db_session.commit()
    return form


def _raw(roll, email):
    return {
        "name": "Activation Student", "roll_number": roll, "email": email, "student_mobile": "9000000000",
        "father_name": "Father", "father_mobile": "9000000001", "address": "123 Test St",
        "high_school_board": "CBSE", "date_of_birth": "2005-01-01",
    }


def test_synced_student_account_is_inactive_until_activated(db_session):
    form = _make_form(db_session)
    submission = registration_sync.sync_submission(db_session, form, "act-resp-1", datetime.now(timezone.utc), _raw("ACT-001", "act1@coresight.edu"))
    assert submission.status == SubmissionStatus.SYNCED

    student = db_session.query(Student).filter(Student.roll_number == "ACT-001").first()
    assert student.user.is_active is False


def test_activation_token_created_on_sync(db_session):
    form = _make_form(db_session)
    registration_sync.sync_submission(db_session, form, "act-resp-2", datetime.now(timezone.utc), _raw("ACT-002", "act2@coresight.edu"))
    student = db_session.query(Student).filter(Student.roll_number == "ACT-002").first()
    token = db_session.query(AccountActivationToken).filter(AccountActivationToken.user_id == student.user_id).first()
    assert token is not None
    assert token.used_at is None


def test_activate_account_sets_real_password_and_activates(db_session):
    form = _make_form(db_session)
    registration_sync.sync_submission(db_session, form, "act-resp-3", datetime.now(timezone.utc), _raw("ACT-003", "act3@coresight.edu"))
    student = db_session.query(Student).filter(Student.roll_number == "ACT-003").first()

    raw_token = activation_service.create_activation_token(db_session, student.user)
    db_session.commit()

    activated_user = activation_service.activate_account(db_session, raw_token, "a-real-password-123")
    assert activated_user.is_active is True
    assert verify_password("a-real-password-123", activated_user.password_hash)


def test_activate_account_token_is_single_use(db_session):
    form = _make_form(db_session)
    registration_sync.sync_submission(db_session, form, "act-resp-4", datetime.now(timezone.utc), _raw("ACT-004", "act4@coresight.edu"))
    student = db_session.query(Student).filter(Student.roll_number == "ACT-004").first()

    raw_token = activation_service.create_activation_token(db_session, student.user)
    db_session.commit()
    activation_service.activate_account(db_session, raw_token, "first-password-123")

    with pytest.raises(HTTPException) as exc_info:
        activation_service.activate_account(db_session, raw_token, "second-password-123")
    assert exc_info.value.status_code == 400


def test_activate_account_expired_token_rejected(db_session):
    form = _make_form(db_session)
    registration_sync.sync_submission(db_session, form, "act-resp-5", datetime.now(timezone.utc), _raw("ACT-005", "act5@coresight.edu"))
    student = db_session.query(Student).filter(Student.roll_number == "ACT-005").first()

    raw_token = activation_service.create_activation_token(db_session, student.user)
    token_row = db_session.query(AccountActivationToken).filter(AccountActivationToken.user_id == student.user_id).first()
    token_row.expires_at = utcnow() - timedelta(hours=1)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        activation_service.activate_account(db_session, raw_token, "a-real-password-123")
    assert exc_info.value.status_code == 400


def test_activate_account_invalid_token_rejected(db_session):
    with pytest.raises(HTTPException) as exc_info:
        activation_service.activate_account(db_session, "not-a-real-token", "a-real-password-123")
    assert exc_info.value.status_code == 400


def test_activate_endpoint_via_api(client, db_session):
    form = _make_form(db_session)
    registration_sync.sync_submission(db_session, form, "act-resp-6", datetime.now(timezone.utc), _raw("ACT-006", "act6@coresight.edu"))
    student = db_session.query(Student).filter(Student.roll_number == "ACT-006").first()
    raw_token = activation_service.create_activation_token(db_session, student.user)
    db_session.commit()

    resp = client.post("/api/auth/activate", json={"token": raw_token, "newPassword": "a-real-password-123"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "student"

    # And the student can now actually log in.
    login_resp = client.post("/api/auth/login", json={"email": "act6@coresight.edu", "password": "a-real-password-123"})
    assert login_resp.status_code == 200


def test_repeated_sync_of_same_response_does_not_duplicate_activation_tokens(db_session):
    form = _make_form(db_session)
    registration_sync.sync_submission(db_session, form, "act-resp-7", datetime.now(timezone.utc), _raw("ACT-007", "act7@coresight.edu"))
    registration_sync.sync_submission(db_session, form, "act-resp-7", datetime.now(timezone.utc), _raw("ACT-007", "act7@coresight.edu"))

    student = db_session.query(Student).filter(Student.roll_number == "ACT-007").first()
    count = db_session.query(AccountActivationToken).filter(AccountActivationToken.user_id == student.user_id).count()
    assert count == 1
