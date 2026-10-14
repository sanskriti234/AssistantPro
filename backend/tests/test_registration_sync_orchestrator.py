import uuid
from unittest.mock import patch

from app.core.security import hash_password
from app.database.models import (
    AcademicSession, AuditLog, Batch, Course, Department, FormStatus,
    RegistrationForm, RegistrationSubmission, Role, SessionStatus, Student, SubmissionStatus, User,
)
from app.services import google_forms_service, registration_sync_orchestrator
from app.services.google_forms_service import GoogleFormsAPIError

FIELD_MAPPING = {
    "name": "q-name", "roll_number": "q-roll", "gender": "q-gender", "date_of_birth": "q-dob",
    "email": "q-email", "student_mobile": "q-mobile", "batch_confirmation": "q-confirm", "semester": "q-sem",
    "father_name": "q-father", "mother_name": "q-mother", "address": "q-address",
    "high_school_board": "q-hs-board", "high_school_institution": "q-hs-inst",
    "high_school_passing_year": "q-hs-year", "high_school_score": "q-hs-score",
    "intermediate_board": "q-int-board", "intermediate_institution": "q-int-inst",
    "intermediate_passing_year": "q-int-year", "intermediate_score": "q-int-score",
}


def _text(question_id, value):
    return question_id, {"textAnswers": {"answers": [{"value": value}]}}


def _fake_response(response_id: str, roll_number: str, email: str) -> dict:
    answers = dict([
        _text("q-name", "Test Student"), _text("q-roll", roll_number), _text("q-gender", "Female"),
        _text("q-dob", "2005-01-01"), _text("q-email", email), _text("q-mobile", "9000000000"),
        _text("q-confirm", "Yes"), _text("q-sem", "3"),
        _text("q-father", "Father"), _text("q-mother", "Mother"), _text("q-address", "Addr"),
        _text("q-hs-board", "CBSE"), _text("q-hs-inst", "School"), _text("q-hs-year", "2019"), _text("q-hs-score", "90"),
        _text("q-int-board", "CBSE"), _text("q-int-inst", "School"), _text("q-int-year", "2021"), _text("q-int-score", "85"),
    ])
    return {"responseId": response_id, "lastSubmittedTime": "2026-08-01T10:00:00Z", "answers": answers}


def _make_form(db_session, field_mapping=FIELD_MAPPING):
    suffix = uuid.uuid4().hex[:8]
    dept = Department(code=f"OR{suffix}", name=f"Orchestrator Dept {suffix}")
    course = Course(code=f"ORC{suffix}", name=f"Orchestrator Course {suffix}", duration_years=4)
    db_session.add_all([dept, course])
    db_session.flush()
    session = AcademicSession(name=f"orch-{suffix}", status=SessionStatus.ACTIVE)
    db_session.add(session)
    db_session.flush()
    batch = Batch(academic_session_id=session.id, course_id=course.id, department_id=dept.id, year=2, section="A", name=f"Orchestrator Batch {suffix}")
    db_session.add(batch)
    db_session.flush()
    admin = User(email=f"orch-admin-{suffix}@coresight.edu", password_hash=hash_password("x"), role=Role.ADMIN)
    db_session.add(admin)
    db_session.flush()
    form = RegistrationForm(
        batch_id=batch.id, google_form_id=f"gform-{suffix}", status=FormStatus.ACTIVE,
        created_by=admin.id, field_mapping=field_mapping,
    )
    db_session.add(form)
    db_session.commit()
    return form, admin


def test_sync_form_creates_new_students_from_responses(db_session):
    form, admin = _make_form(db_session)
    responses = [_fake_response("r1", "ORC-001", "orc1@coresight.edu"), _fake_response("r2", "ORC-002", "orc2@coresight.edu")]

    with patch.object(google_forms_service, "fetch_responses", return_value=responses):
        summary = registration_sync_orchestrator.sync_form(db_session, form, triggered_by=admin.id)

    assert summary["responses_found"] == 2
    assert summary["synced"] == 2
    assert db_session.query(Student).filter(Student.roll_number.in_(["ORC-001", "ORC-002"])).count() == 2


def test_sync_form_is_idempotent_on_rerun(db_session):
    form, admin = _make_form(db_session)
    responses = [_fake_response("r3", "ORC-003", "orc3@coresight.edu")]

    with patch.object(google_forms_service, "fetch_responses", return_value=responses):
        summary1 = registration_sync_orchestrator.sync_form(db_session, form, triggered_by=admin.id)
        summary2 = registration_sync_orchestrator.sync_form(db_session, form, triggered_by=admin.id)

    assert summary1["synced"] == 1
    assert summary2["synced"] == 0  # already SYNCED - not reprocessed
    assert db_session.query(Student).filter(Student.roll_number == "ORC-003").count() == 1
    assert db_session.query(RegistrationSubmission).filter(RegistrationSubmission.google_response_id == "r3").count() == 1


def test_sync_form_rejects_response_missing_required_field(db_session):
    form, admin = _make_form(db_session)
    response = _fake_response("r4", "ORC-004", "orc4@coresight.edu")
    del response["answers"]["q-father"]

    with patch.object(google_forms_service, "fetch_responses", return_value=[response]):
        summary = registration_sync_orchestrator.sync_form(db_session, form, triggered_by=admin.id)

    assert summary["rejected"] == 1
    assert summary["synced"] == 0
    submission = db_session.query(RegistrationSubmission).filter(RegistrationSubmission.google_response_id == "r4").first()
    assert submission.status == SubmissionStatus.REJECTED
    assert submission.error_message is not None


def test_sync_form_without_field_mapping_rejects_all_responses(db_session):
    form, admin = _make_form(db_session, field_mapping=None)
    with patch.object(google_forms_service, "fetch_responses", return_value=[_fake_response("r5", "ORC-005", "orc5@coresight.edu")]):
        summary = registration_sync_orchestrator.sync_form(db_session, form, triggered_by=admin.id)
    assert summary["rejected"] == 1


def test_sync_all_active_forms_one_failing_form_does_not_stop_others(db_session):
    form1, admin = _make_form(db_session)
    form2, _ = _make_form(db_session)

    def fake_fetch(google_form_id, forms_client=None):
        if google_form_id == form1.google_form_id:
            raise GoogleFormsAPIError("simulated Google API outage")
        if google_form_id == form2.google_form_id:
            return [_fake_response("r6", "ORC-006", "orc6@coresight.edu")]
        return []

    with patch.object(google_forms_service, "fetch_responses", side_effect=fake_fetch):
        totals = registration_sync_orchestrator.sync_all_active_forms(db_session, triggered_by=admin.id)

    assert totals["forms_checked"] >= 2
    assert totals["forms_with_errors"] >= 1
    # form2 was still processed despite form1 failing:
    assert db_session.query(Student).filter(Student.roll_number == "ORC-006").count() == 1

    failed_audit = db_session.query(AuditLog).filter(AuditLog.action == "REGISTRATION_SYNC_FAILED", AuditLog.entity_id == str(form1.id)).first()
    assert failed_audit is not None


def test_sync_all_active_forms_only_checks_active_forms(db_session):
    form, admin = _make_form(db_session)
    form.status = FormStatus.INACTIVE
    db_session.commit()

    with patch.object(google_forms_service, "fetch_responses", return_value=[]) as mock_fetch:
        registration_sync_orchestrator.sync_all_active_forms(db_session, triggered_by=admin.id)

    called_form_ids = [call.args[0] for call in mock_fetch.call_args_list]
    assert form.google_form_id not in called_form_ids


def _login(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


def test_admin_sync_endpoint(client, db_session, make_user):
    form, _ = _make_form(db_session)
    make_user("sync-admin@coresight.edu", Role.ADMIN, password="pw")
    token = _login(client, "sync-admin@coresight.edu", "pw")

    def fake_fetch(google_form_id, forms_client=None):
        if google_form_id == form.google_form_id:
            return [_fake_response("r7", "ORC-007", "orc7@coresight.edu")]
        return []

    with patch.object(google_forms_service, "fetch_responses", side_effect=fake_fetch):
        resp = client.post("/api/registration/sync", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["synced"] >= 1


def test_faculty_cannot_trigger_sync(client, db_session, make_user):
    make_user("sync-faculty@coresight.edu", Role.FACULTY, password="pw")
    token = _login(client, "sync-faculty@coresight.edu", "pw")
    resp = client.post("/api/registration/sync", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_student_cannot_trigger_sync(client, db_session, make_user):
    make_user("sync-student@coresight.edu", Role.STUDENT, password="pw")
    token = _login(client, "sync-student@coresight.edu", "pw")
    resp = client.post("/api/registration/sync", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_per_form_sync_endpoint(client, db_session, make_user):
    form, _ = _make_form(db_session)
    make_user("sync-admin2@coresight.edu", Role.ADMIN, password="pw")
    token = _login(client, "sync-admin2@coresight.edu", "pw")

    with patch.object(google_forms_service, "fetch_responses", return_value=[_fake_response("r8", "ORC-008", "orc8@coresight.edu")]):
        resp = client.post(f"/api/registration/forms/{form.id}/sync", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json()["synced"] == 1


def test_per_form_sync_invalid_form_returns_404(client, make_user):
    make_user("sync-admin3@coresight.edu", Role.ADMIN, password="pw")
    token = _login(client, "sync-admin3@coresight.edu", "pw")
    resp = client.post(f"/api/registration/forms/{uuid.uuid4()}/sync", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
