import uuid
from datetime import datetime, timezone

from app.database.models import (
    AcademicSession, Batch, Course, Department, FormStatus,
    RegistrationForm, RegistrationSubmission, Role, SessionStatus, Student, StudentEnrollment, User,
)
from app.services import registration_sync
from app.core.security import hash_password


def _make_form(db_session):
    suffix = uuid.uuid4().hex[:8]
    dept = Department(code=f"RS{suffix}", name=f"RegSync Dept {suffix}")
    course = Course(code=f"RSC{suffix}", name=f"RegSync Course {suffix}", duration_years=4)
    db_session.add_all([dept, course])
    db_session.flush()
    session = AcademicSession(name=f"regsync-{suffix}", status=SessionStatus.ACTIVE)
    db_session.add(session)
    db_session.flush()
    batch = Batch(academic_session_id=session.id, course_id=course.id, department_id=dept.id, year=1, section="A", name=f"RegSync Batch {suffix}")
    db_session.add(batch)
    db_session.flush()

    admin_user = User(email=f"regsync-admin-{suffix}@coresight.edu", password_hash=hash_password("x"), role=Role.ADMIN)
    db_session.add(admin_user)
    db_session.flush()

    form = RegistrationForm(batch_id=batch.id, google_form_id=f"form-{suffix}", status=FormStatus.ACTIVE, created_by=admin_user.id)
    db_session.add(form)
    db_session.commit()
    return form


def _raw(roll="RS-001", email="newstudent@coresight.edu"):
    return {
        "name": "New Student",
        "roll_number": roll,
        "email": email,
        "student_mobile": "9000000000",
        "father_name": "Father Name",
        "father_mobile": "9000000001",
        "address": "123 Test Street",
        "high_school_board": "CBSE",
    }


def test_sync_creates_normalized_student_records(db_session):
    form = _make_form(db_session)
    submission = registration_sync.sync_submission(
        db_session, form, "resp-1", datetime.now(timezone.utc), _raw()
    )
    assert submission.status.value == "SYNCED"

    student = db_session.query(Student).filter(Student.roll_number == "RS-001").first()
    assert student is not None
    assert student.full_name == "New Student"
    assert len(student.contacts) == 2  # STUDENT + FATHER
    assert student.address is not None
    assert len(student.qualifications) == 1
    assert len(student.enrollments) == 1


def test_sync_is_idempotent_on_google_response_id(db_session):
    form = _make_form(db_session)
    s1 = registration_sync.sync_submission(db_session, form, "resp-2", datetime.now(timezone.utc), _raw(roll="RS-002", email="dup1@coresight.edu"))
    s2 = registration_sync.sync_submission(db_session, form, "resp-2", datetime.now(timezone.utc), _raw(roll="RS-002", email="dup1@coresight.edu"))
    assert s1.id == s2.id

    count = db_session.query(RegistrationSubmission).filter(RegistrationSubmission.google_response_id == "resp-2").count()
    assert count == 1

    student_count = db_session.query(Student).filter(Student.roll_number == "RS-002").count()
    assert student_count == 1


def test_sync_rejects_duplicate_roll_number_from_different_response(db_session):
    form = _make_form(db_session)
    registration_sync.sync_submission(db_session, form, "resp-3", datetime.now(timezone.utc), _raw(roll="RS-003", email="a@coresight.edu"))

    # NOTE: this now returns a DUPLICATE-status submission rather than
    # raising - see registration_sync.py module docstring and
    # tests/test_registration_sync_v2.py, which covers this in depth. The
    # important guarantee (no second student created) is unchanged.
    from app.database.models import SubmissionStatus, Student

    result = registration_sync.sync_submission(db_session, form, "resp-4", datetime.now(timezone.utc), _raw(roll="RS-003", email="b@coresight.edu"))
    assert result.status == SubmissionStatus.DUPLICATE
    assert db_session.query(Student).filter(Student.roll_number == "RS-003").count() == 1


def test_failed_submission_can_be_retried_without_duplicating(db_session):
    """
    A submission stuck in a non-terminal state (simulating an interrupted
    prior attempt) is reprocessed in place on retry - not duplicated -
    because google_response_id is looked up first and is UNIQUE.
    """
    from app.database.models import RegistrationSubmission, SubmissionStatus

    form = _make_form(db_session)
    raw = _raw(roll="RS-RETRY", email="retry@coresight.edu")

    # Simulate a prior attempt that got interrupted after creating the
    # PENDING row but before finishing (e.g. process crash).
    stuck = RegistrationSubmission(
        form_id=form.id, google_response_id="resp-retry", submitted_at=datetime.now(timezone.utc),
        raw_response=raw, status=SubmissionStatus.FAILED, error_message="simulated prior crash",
    )
    db_session.add(stuck)
    db_session.commit()

    result = registration_sync.sync_submission(db_session, form, "resp-retry", datetime.now(timezone.utc), raw)

    assert result.status == SubmissionStatus.SYNCED
    assert result.id == stuck.id  # same row, reused - not a second submission
    count = db_session.query(RegistrationSubmission).filter(RegistrationSubmission.google_response_id == "resp-retry").count()
    assert count == 1


def test_synced_submission_is_never_reprocessed(db_session):
    form = _make_form(db_session)
    raw = _raw(roll="RS-TERM", email="terminal@coresight.edu")
    first = registration_sync.sync_submission(db_session, form, "resp-terminal", datetime.now(timezone.utc), raw)
    assert first.status.value == "SYNCED"

    # Even with different (nonsense) data, a SYNCED response is returned
    # unchanged rather than reprocessed.
    second = registration_sync.sync_submission(db_session, form, "resp-terminal", datetime.now(timezone.utc), {"roll_number": "DIFFERENT"})
    assert second.id == first.id
    assert second.status.value == "SYNCED"
