import uuid
from unittest.mock import MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials

from app.core.config import Settings
from app.core.security import hash_password
from app.database.models import (
    AcademicSession, AuditLog, Batch, Course, Department,
    FormStatus, RegistrationForm, Role, SessionStatus, User,
)
from app.services import google_forms_service, registration_form_service
from app.services.google_forms_service import (
    FORMS_SCOPES,
    GoogleFormsAPIError,
    GoogleFormsNotConfigured,
    build_form_definition,
    get_forms_client,
    get_google_credentials,
)


def _make_batch(db_session, name="Form Test Batch"):
    suffix = uuid.uuid4().hex[:8]
    dept = Department(code=f"FRM{suffix}", name=f"Form Test Department {suffix}")
    course = Course(code=f"FRMC{suffix}", name=f"{name} {suffix}", duration_years=4)
    db_session.add_all([dept, course])
    db_session.flush()
    session = AcademicSession(name=f"form-test-{suffix}", status=SessionStatus.ACTIVE)
    db_session.add(session)
    db_session.flush()
    batch = Batch(academic_session_id=session.id, course_id=course.id, department_id=dept.id, year=3, section="A", name=f"{name} {suffix}")
    db_session.add(batch)
    db_session.commit()
    return batch


def _login(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


# --- Pure form-definition content tests (no network, no mocking needed) ----

def test_form_definition_contains_required_personal_fields(db_session):
    batch = _make_batch(db_session)
    definition = build_form_definition(batch)
    titles = [item["title"] for item in definition["items"]]

    for required_title in ["Full Name", "Roll Number", "Gender", "Date of Birth", "Student Email", "Student Mobile Number"]:
        assert required_title in titles

    full_name_item = next(i for i in definition["items"] if i["title"] == "Full Name")
    assert full_name_item["questionItem"]["question"]["required"] is True


def test_form_definition_diploma_fields_are_optional(db_session):
    batch = _make_batch(db_session)
    definition = build_form_definition(batch)
    diploma_items = [
        i for i in definition["items"]
        if i["title"].startswith("Diploma") and "questionItem" in i
    ]
    assert len(diploma_items) > 0
    for item in diploma_items:
        assert item["questionItem"]["question"]["required"] is False


def test_form_definition_high_school_and_intermediate_required(db_session):
    batch = _make_batch(db_session)
    definition = build_form_definition(batch)
    for prefix in ["High School Board", "Intermediate Board"]:
        item = next(i for i in definition["items"] if i["title"] == prefix)
        assert item["questionItem"]["question"]["required"] is True


def test_form_definition_uses_batch_as_authoritative_academic_context(db_session):
    batch = _make_batch(db_session, name="CSE AIML 2027")
    definition = build_form_definition(batch)
    academic_section = next(i for i in definition["items"] if i["title"] == "Academic Information")
    assert batch.name in academic_section["description"]
    assert batch.department.name in academic_section["description"]
    # No editable "Course"/"Department"/"Year" free-text fields exist - students
    # cannot type a different academic context than their assigned batch.
    titles = [i["title"] for i in definition["items"]]
    assert "Department" not in titles
    assert "Course" not in titles


def test_form_title_and_description_are_batch_specific(db_session):
    batch = _make_batch(db_session, name="ECE 2028")
    title = google_forms_service.build_form_title(batch)
    description = google_forms_service.build_form_description(batch)
    assert batch.name in title
    assert batch.section in title
    assert batch.name in description


def test_form_definition_contains_no_file_upload_question(db_session):
    """Google Forms API v1 cannot create file_upload questions."""
    batch = _make_batch(db_session)
    definition = build_form_definition(batch)

    # Must contain no fileUploadQuestion in items
    for item in definition["items"]:
        question = item.get("questionItem", {}).get("question", {})
        assert "fileUploadQuestion" not in question, f"Found fileUploadQuestion in item: {item}"

    # Must contain no profile_photo_file_id in field_keys
    assert "profile_photo_file_id" not in definition["field_keys"]


# --- OAuth refresh-token & Explicit Credential tests ------------------------

def test_oauth_refresh_token_credential_construction(monkeypatch):
    """Verifies that Credentials are built explicitly from OAuth configuration without ADC."""
    fake_settings = Settings(
        google_oauth_client_id="test-client-id.apps.googleusercontent.com",
        google_oauth_client_secret="test-client-secret",
        google_oauth_refresh_token="1//test-refresh-token",
    )
    monkeypatch.setattr(google_forms_service, "get_settings", lambda: fake_settings)

    creds = get_google_credentials()
    assert isinstance(creds, Credentials)
    assert creds.client_id == "test-client-id.apps.googleusercontent.com"
    assert creds.client_secret == "test-client-secret"
    assert creds.refresh_token == "1//test-refresh-token"
    assert creds.token_uri == "https://oauth2.googleapis.com/token"
    assert set(creds.scopes) == set(FORMS_SCOPES)


def test_forms_client_creation_with_explicit_credentials(monkeypatch):
    """Verifies that build('forms', 'v1', credentials=...) receives explicit Credentials."""
    fake_settings = Settings(
        google_oauth_client_id="test-client-id.apps.googleusercontent.com",
        google_oauth_client_secret="test-client-secret",
        google_oauth_refresh_token="1//test-refresh-token",
    )
    monkeypatch.setattr(google_forms_service, "get_settings", lambda: fake_settings)

    with patch("googleapiclient.discovery.build") as mock_build:
        mock_build.return_value = MagicMock()
        get_forms_client()

    assert mock_build.called
    call_args, call_kwargs = mock_build.call_args
    assert call_args == ("forms", "v1")
    assert isinstance(call_kwargs["credentials"], Credentials)
    assert call_kwargs["credentials"].client_id == "test-client-id.apps.googleusercontent.com"
    assert call_kwargs["cache_discovery"] is False


def test_no_adc_dependency(monkeypatch, db_session):
    """Ensures Application Default Credentials (ADC) is never accessed."""
    fake_settings = Settings(
        google_oauth_client_id="test-client-id.apps.googleusercontent.com",
        google_oauth_client_secret="test-client-secret",
        google_oauth_refresh_token="1//test-refresh-token",
    )
    monkeypatch.setattr(google_forms_service, "get_settings", lambda: fake_settings)

    def fail_on_adc(*args, **kwargs):
        raise AssertionError("Application Default Credentials (ADC) must not be loaded!")

    with patch("google.auth.default", side_effect=fail_on_adc):
        creds = get_google_credentials()
        assert creds.client_id == "test-client-id.apps.googleusercontent.com"

        with patch("googleapiclient.discovery.build") as mock_build:
            mock_client = MagicMock()
            mock_build.return_value = mock_client
            client = get_forms_client()
            assert client == mock_client


def test_successful_form_generation_request_structure(db_session):
    """
    Verifies that create_registration_form issues a single batchUpdate with
    NO file_upload questions and correctly maps question IDs.
    """
    batch = _make_batch(db_session)
    definition = build_form_definition(batch)
    num_items = len(definition["items"])

    mock_client = MagicMock()
    mock_forms = mock_client.forms.return_value
    mock_forms.create.return_value.execute.return_value = {"formId": "gform-test-123"}

    # Mock batchUpdate replies: 1 reply for updateFormInfo, then replies for each createItem
    replies = [{}] + [{"createItem": {"questionId": [f"qid-{i}"]}} for i in range(num_items)]
    mock_forms.batchUpdate.return_value.execute.return_value = {"replies": replies}
    mock_forms.get.return_value.execute.return_value = {
        "responderUri": "https://docs.google.com/forms/d/gform-test-123/viewform"
    }

    result = google_forms_service.create_registration_form(batch, forms_client=mock_client)

    # Exactly 1 batchUpdate call (single-pass, no second pass for file upload)
    assert mock_forms.batchUpdate.call_count == 1
    batch_kwargs = mock_forms.batchUpdate.call_args[1]
    assert batch_kwargs["formId"] == "gform-test-123"

    requests = batch_kwargs["body"]["requests"]
    assert "updateFormInfo" in requests[0]
    for req in requests[1:]:
        assert "createItem" in req
        item = req["createItem"]["item"]
        question = item.get("questionItem", {}).get("question", {})
        assert "fileUploadQuestion" not in question

    assert result["google_form_id"] == "gform-test-123"
    assert result["form_url"] == "https://docs.google.com/forms/d/gform-test-123/viewform"
    assert "profile_photo_file_id" not in result["field_mapping"]
    assert "name" in result["field_mapping"]
    assert result["field_mapping"]["name"] == "qid-1"  # qid-0 is Personal Information section header


# --- Orchestration tests (Google API mocked) --------------------------------

def test_generate_form_not_configured_raises(db_session, monkeypatch):
    batch = _make_batch(db_session)
    admin = User(email=f"admin-{uuid.uuid4().hex[:6]}@coresight.edu", password_hash=hash_password("x"), role=Role.ADMIN)
    db_session.add(admin)
    db_session.commit()

    unconfigured = Settings(google_oauth_client_id="", google_oauth_client_secret="", google_oauth_refresh_token="")
    monkeypatch.setattr(google_forms_service, "get_settings", lambda: unconfigured)

    with pytest.raises(GoogleFormsNotConfigured):
        registration_form_service.generate_or_get_form(db_session, batch, admin.id)

    assert db_session.query(RegistrationForm).filter(RegistrationForm.batch_id == batch.id).first() is None


def test_generate_form_success_persists_and_audits(db_session):
    batch = _make_batch(db_session)
    admin = User(email=f"admin-{uuid.uuid4().hex[:6]}@coresight.edu", password_hash=hash_password("x"), role=Role.ADMIN)
    db_session.add(admin)
    db_session.commit()

    fake_result = {
        "google_form_id": "fake-form-id-123",
        "form_url": "https://docs.google.com/forms/d/fake-form-id-123/viewform",
        "edit_url": "https://docs.google.com/forms/d/fake-form-id-123/edit",
        "field_mapping": {"name": "qid-name"},
    }

    with patch.object(google_forms_service, "create_registration_form", return_value=fake_result) as mock_create:
        form, created = registration_form_service.generate_or_get_form(db_session, batch, admin.id)

    assert created is True
    assert mock_create.call_count == 1
    assert form.google_form_id == "fake-form-id-123"
    assert form.form_url == fake_result["form_url"]
    assert form.status == FormStatus.ACTIVE
    assert form.google_sheet_id is None  # by design - see google_forms_service docstring

    persisted = db_session.query(RegistrationForm).filter(RegistrationForm.batch_id == batch.id).first()
    assert persisted is not None
    assert persisted.google_form_id == "fake-form-id-123"

    audit = db_session.query(AuditLog).filter(AuditLog.action == "REGISTRATION_FORM_CREATED", AuditLog.entity_id == str(form.id)).first()
    assert audit is not None
    assert (audit.metadata_json or {}).get("batch_id") == str(batch.id)


def test_generate_form_idempotent_returns_existing_without_duplicate_or_second_google_call(db_session):
    batch = _make_batch(db_session)
    admin = User(email=f"admin-{uuid.uuid4().hex[:6]}@coresight.edu", password_hash=hash_password("x"), role=Role.ADMIN)
    db_session.add(admin)
    db_session.commit()

    fake_result = {"google_form_id": "idempotent-form", "form_url": "https://forms.example/idempotent", "edit_url": "https://forms.example/idempotent/edit"}

    with patch.object(google_forms_service, "create_registration_form", return_value=fake_result) as mock_create:
        form1, created1 = registration_form_service.generate_or_get_form(db_session, batch, admin.id)
        form2, created2 = registration_form_service.generate_or_get_form(db_session, batch, admin.id)

    assert created1 is True
    assert created2 is False
    assert form1.id == form2.id
    assert mock_create.call_count == 1  # Google was only called once

    count = db_session.query(RegistrationForm).filter(RegistrationForm.batch_id == batch.id).count()
    assert count == 1

    already_exists_audit = db_session.query(AuditLog).filter(AuditLog.action == "FORM_ALREADY_EXISTS").first()
    assert already_exists_audit is not None


def test_generate_form_google_failure_leaves_no_db_row(db_session):
    batch = _make_batch(db_session)
    admin = User(email=f"admin-{uuid.uuid4().hex[:6]}@coresight.edu", password_hash=hash_password("x"), role=Role.ADMIN)
    db_session.add(admin)
    db_session.commit()

    with patch.object(google_forms_service, "create_registration_form", side_effect=GoogleFormsAPIError("boom")):
        with pytest.raises(GoogleFormsAPIError):
            registration_form_service.generate_or_get_form(db_session, batch, admin.id)

    assert db_session.query(RegistrationForm).filter(RegistrationForm.batch_id == batch.id).first() is None
    # No misleading success audit entry either.
    created_audits = [
        l for l in db_session.query(AuditLog).filter(
            AuditLog.action == "REGISTRATION_FORM_CREATED",
            AuditLog.entity_type == "registration_form",
        ).all()
        if (l.metadata_json or {}).get("batch_id") == str(batch.id)
    ]
    assert len(created_audits) == 0


# --- API-layer authorization + response shape tests -------------------------

def test_admin_can_generate_form_via_api(client, db_session, make_user):
    batch = _make_batch(db_session)
    make_user("form-admin@coresight.edu", Role.ADMIN, password="pw")
    token = _login(client, "form-admin@coresight.edu", "pw")

    fake_result = {"google_form_id": "api-form-1", "form_url": "https://forms.example/api-form-1", "edit_url": "x"}
    with patch.object(google_forms_service, "create_registration_form", return_value=fake_result):
        resp = client.post(f"/api/batches/{batch.id}/generate-form", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["formStatus"] == "active"
    assert body["formUrl"] == fake_result["form_url"]
    assert body["googleFormId"] == "api-form-1"


def test_faculty_cannot_generate_form(client, db_session, make_user):
    batch = _make_batch(db_session)
    make_user("form-faculty@coresight.edu", Role.FACULTY, password="pw")
    token = _login(client, "form-faculty@coresight.edu", "pw")
    resp = client.post(f"/api/batches/{batch.id}/generate-form", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_student_cannot_generate_form(client, db_session, make_user):
    batch = _make_batch(db_session)
    make_user("form-student@coresight.edu", Role.STUDENT, password="pw")
    token = _login(client, "form-student@coresight.edu", "pw")
    resp = client.post(f"/api/batches/{batch.id}/generate-form", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_generate_form_invalid_batch_returns_404(client, make_user):
    make_user("form-admin-404@coresight.edu", Role.ADMIN, password="pw")
    token = _login(client, "form-admin-404@coresight.edu", "pw")
    resp = client.post(f"/api/batches/{uuid.uuid4()}/generate-form", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_generate_form_not_configured_returns_503(client, db_session, make_user, monkeypatch):
    batch = _make_batch(db_session)
    make_user("form-admin-503@coresight.edu", Role.ADMIN, password="pw")
    token = _login(client, "form-admin-503@coresight.edu", "pw")

    unconfigured = Settings(google_oauth_client_id="", google_oauth_client_secret="", google_oauth_refresh_token="")
    monkeypatch.setattr(google_forms_service, "get_settings", lambda: unconfigured)

    resp = client.post(f"/api/batches/{batch.id}/generate-form", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503

