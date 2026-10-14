"""
Google Forms integration.

LIMITATION (see backend/README.md "Google Cloud setup" and "Known
limitations"): this sandbox's network egress does not include
googleapis.com, so a live call to forms.create()/batchUpdate() has not been
exercised here. What's implemented and unit-tested without any network
access is (a) the form definition itself - build_form_definition() is a
pure function, fully covered by tests that assert every required question,
the optional-diploma section, and batch-authoritative academic fields are
present - and (b) create_registration_form()/fetch_responses(), written
against the documented Forms API v1 request/response shapes so a real
credential swap-in requires no code changes. See backend/README.md
"Google Cloud setup" for exact setup steps and the optional integration
test that exercises this for real once credentials are configured.

Design choice: no Google Sheet is created or referenced. The Forms API v1
supports reading responses directly via forms.responses.list()/get() -
there is no documented Forms API method to provision a *linked spreadsheet*
destination (that has historically been a Drive-UI-only action). Rather
than fabricate a google_sheet_id, this service syncs straight from
responses.list() and registration_forms.google_sheet_id stays NULL, per
the project's own instruction not to fabricate a sheet ID.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.database.models import Batch

logger = logging.getLogger("coresight.google_forms")

FORMS_SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleFormsNotConfigured(Exception):
    """Raised when GOOGLE_OAUTH_* environment variables are not set."""


class GoogleFormsAPIError(Exception):
    """
    Raised when a Google API call fails. The message is safe to show to an
    admin (no tokens/secrets/stack traces).
    """


# ---------------------------------------------------------------------------
# Pure, network-free: the actual form content. Kept separate from the API
# call so it's fully unit-testable without credentials.
# ---------------------------------------------------------------------------

def _text_question(title: str, *, required: bool = False, paragraph: bool = False) -> dict[str, Any]:
    return {
        "title": title,
        "questionItem": {"question": {"required": required, "textQuestion": {"paragraph": paragraph}}},
    }


def _choice_question(title: str, options: list[str], *, required: bool = False) -> dict[str, Any]:
    return {
        "title": title,
        "questionItem": {
            "question": {
                "required": required,
                "choiceQuestion": {"type": "RADIO", "options": [{"value": o} for o in options]},
            }
        },
    }


def _date_question(title: str, *, required: bool = False) -> dict[str, Any]:
    return {
        "title": title,
        "questionItem": {"question": {"required": required, "dateQuestion": {"includeYear": True}}},
    }


def _section_header(title: str, description: str = "") -> dict[str, Any]:
    return {"title": title, "description": description, "pageBreakItem": {}}


def build_form_title(batch: Batch) -> str:
    return f"CoreSight Student Registration \u2014 {batch.name} \u2014 Section {batch.section}"


def build_form_description(batch: Batch) -> str:
    return (
        f"This form registers students into CoreSight for {batch.name} "
        f"(Section {batch.section}). Please submit accurate information \u2014 it "
        "will be used to create your CoreSight enrollment. Profile photo and "
        "biometric face enrollment will be completed directly in CoreSight. "
        "Please submit this form only once."
    )


def build_form_definition(batch: Batch) -> dict[str, Any]:
    """
    Builds the full set of form items. Google Forms API v1 does not support
    programmatic creation of file_upload questions; student profile photo and
    biometric face enrollment are handled inside CoreSight's authenticated
    camera flow. Course/department/year are shown to the student as read-only
    context text, never as editable fields: the batch (registration_forms.batch_id)
    remains the authoritative source and the backend ignores any
    student-typed value for these, per project policy.

    Each item is paired with a `field_key` (or None for section headers /
    unmapped items) in the same order. create_registration_form() zips this
    against the Google API's per-item creation replies to build a
    deterministic {field_key: google_question_id} mapping, persisted as
    registration_forms.field_mapping - synchronization parses responses by
    that questionId, never by matching question text (see
    registration_response_parser.py).
    """
    pairs: list[tuple[dict[str, Any], str | None]] = []

    pairs.append((_section_header("Personal Information", "All fields in this section are required."), None))
    pairs.append((_text_question("Full Name", required=True), "name"))
    pairs.append((_text_question("Roll Number", required=True), "roll_number"))
    pairs.append((_choice_question("Gender", ["Male", "Female", "Other", "Prefer not to say"], required=True), "gender"))
    pairs.append((_date_question("Date of Birth", required=True), "date_of_birth"))
    pairs.append((_text_question("Student Email", required=True), "email"))
    pairs.append((_text_question("Student Mobile Number", required=True), "student_mobile"))

    pairs.append((_section_header(
        "Academic Information",
        f"You are registering for: {batch.name}, Department: {batch.department.name}, "
        f"Year: {batch.year}, Section: {batch.section}. These are fixed for this "
        "form and cannot be changed here - contact your administrator if incorrect.",
    ), None))
    pairs.append((_text_question(
        f"Confirm you are registering for {batch.name} (type \u201cYes\u201d to confirm)", required=True
    ), "batch_confirmation"))
    pairs.append((_text_question("Semester", required=True), "semester"))

    pairs.append((_section_header("Family Information", "All fields in this section are required."), None))
    pairs.append((_text_question("Father Name", required=True), "father_name"))
    pairs.append((_text_question("Mother Name", required=True), "mother_name"))
    pairs.append((_text_question("Parent/Guardian Name (if applicable)", required=False), "guardian_name"))
    pairs.append((_text_question("Parent/Guardian Mobile Number", required=False), "guardian_mobile"))

    pairs.append((_section_header("Address", "All fields in this section are required."), None))
    pairs.append((_text_question("Complete Address", required=True, paragraph=True), "address"))

    pairs.append((_section_header("High School Qualification", "All fields in this section are required."), None))
    pairs.append((_text_question("High School Board", required=True), "high_school_board"))
    pairs.append((_text_question("High School Institution/School", required=True), "high_school_institution"))
    pairs.append((_text_question("High School Passing Year", required=True), "high_school_passing_year"))
    pairs.append((_text_question("High School Percentage/CGPA", required=True), "high_school_score"))
    pairs.append((_text_question("High School Roll Number (if applicable)", required=False), "high_school_roll_number"))

    pairs.append((_section_header("Intermediate Qualification", "All fields in this section are required."), None))
    pairs.append((_text_question("Intermediate Board", required=True), "intermediate_board"))
    pairs.append((_text_question("Intermediate Institution/School", required=True), "intermediate_institution"))
    pairs.append((_text_question("Intermediate Passing Year", required=True), "intermediate_passing_year"))
    pairs.append((_text_question("Intermediate Percentage/CGPA", required=True), "intermediate_score"))
    pairs.append((_text_question("Intermediate Roll Number (if applicable)", required=False), "intermediate_roll_number"))

    pairs.append((_section_header(
        "Diploma Qualification (Optional)",
        "Leave this section blank if you do not have a diploma.",
    ), None))
    pairs.append((_text_question("Diploma Board/University", required=False), "diploma_board"))
    pairs.append((_text_question("Diploma Institution", required=False), "diploma_institution"))
    pairs.append((_text_question("Diploma Course", required=False), "diploma_course"))
    pairs.append((_text_question("Diploma Passing Year", required=False), "diploma_passing_year"))
    pairs.append((_text_question("Diploma Percentage/CGPA", required=False), "diploma_score"))
    pairs.append((_text_question("Diploma Roll Number (if applicable)", required=False), "diploma_roll_number"))

    return {
        "info": {"title": build_form_title(batch), "documentTitle": build_form_title(batch)},
        "items": [p[0] for p in pairs],
        "field_keys": [p[1] for p in pairs],
        "description": build_form_description(batch),
    }


# ---------------------------------------------------------------------------
# Network-touching: the real Google API calls.
# ---------------------------------------------------------------------------

def get_google_credentials():
    """
    Constructs explicit Google OAuth credentials using the configured
    GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, and GOOGLE_OAUTH_REFRESH_TOKEN.
    Never relies on Application Default Credentials (ADC) or service account keys.
    """
    settings = get_settings()
    if not settings.google_forms_configured:
        raise GoogleFormsNotConfigured(
            "Google Forms integration is not configured "
            "(GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET / GOOGLE_OAUTH_REFRESH_TOKEN)."
        )
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=settings.google_oauth_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=FORMS_SCOPES,
    )


_build_credentials = get_google_credentials


def get_forms_client(credentials=None):
    """
    Builds a Google Forms API v1 client with explicit credentials.
    """
    from googleapiclient.discovery import build

    creds = credentials if credentials is not None else get_google_credentials()
    return build("forms", "v1", credentials=creds, cache_discovery=False)


_build_forms_client = get_forms_client


def create_registration_form(batch: Batch, *, forms_client=None) -> dict[str, str]:
    """
    Creates the Google Form for one batch: forms.create() to establish the
    form (title only - the API restricts what create() accepts), then
    forms.batchUpdate() to add the description and every question in a
    single pass.

    Google Forms API does not support programmatic creation of file_upload
    questions, so profile photos are not collected in the Google Form; student
    profile photos and biometric face enrollment occur inside CoreSight's
    camera-based enrollment flow.

    field_mapping is built from the ACTUAL questionId values the Forms API
    returns in each createItem reply - never invented, never matched by
    question text - and is the deterministic mapping
    registration_response_parser.py uses to read responses back later, so a
    question's title can change without breaking synchronization.

    Raises GoogleFormsNotConfigured / GoogleFormsAPIError - never leaks
    credentials or raw Google error internals to the caller.
    """
    logger.info("FORM_GENERATION_STARTED batch_id=%s", batch.id)

    try:
        client = forms_client or get_forms_client()
        definition = build_form_definition(batch)

        from googleapiclient.errors import HttpError

        created = client.forms().create(body={"info": definition["info"]}).execute()
        form_id = created["formId"]

        requests = [{"updateFormInfo": {
            "info": {"description": definition["description"]},
            "updateMask": "description",
        }}]
        requests += [
            {"createItem": {"item": item, "location": {"index": i}}}
            for i, item in enumerate(definition["items"])
        ]
        batch_result = client.forms().batchUpdate(formId=form_id, body={"requests": requests}).execute()

        # replies[0] is the updateFormInfo reply (no questionId); the rest
        # line up 1:1 with definition["items"]/["field_keys"] in order.
        field_mapping: dict[str, str] = {}
        item_replies = batch_result.get("replies", [])[1:]
        for field_key, reply in zip(definition["field_keys"], item_replies):
            if field_key is None:
                continue
            question_ids = (reply or {}).get("createItem", {}).get("questionId", [])
            if question_ids:
                field_mapping[field_key] = question_ids[0]

        result = client.forms().get(formId=form_id).execute()
        form_url = result.get("responderUri", f"https://docs.google.com/forms/d/{form_id}/viewform")

        logger.info("FORM_GENERATED batch_id=%s google_form_id=%s field_count=%s", batch.id, form_id, len(field_mapping))
        return {
            "google_form_id": form_id,
            "form_url": form_url,
            "edit_url": f"https://docs.google.com/forms/d/{form_id}/edit",
            "field_mapping": field_mapping,
        }
    except GoogleFormsNotConfigured:
        raise
    except HttpError as e:  # type: ignore[name-defined]
        logger.error(
            "FORM_GENERATION_FAILED batch_id=%s reason=google_api_error status=%s error=%s",
            batch.id,
            getattr(e, "status_code", "?"),
            getattr(e, "content", str(e)),
        )        
        raise GoogleFormsAPIError("Google Forms API request failed. Please try again or contact an administrator.") from e
    except Exception as e:
        logger.exception(
            "FORM_GENERATION_FAILED batch_id=%s error_type=%s error=%s",
            batch.id,
            type(e).__name__,
            str(e),
        )
        raise GoogleFormsAPIError(
            "Could not create the Google Form. "
            "Please check the backend logs."
        ) from e

def fetch_responses(google_form_id: str, *, forms_client=None) -> list[dict[str, Any]]:
    """
    Pulls responses directly via forms.responses.list() - see module
    docstring for why no Google Sheet is used. Returns the raw Forms API
    response objects; registration_sync.sync_submission() is responsible
    for mapping them into CoreSight's normalized fields.
    """
    try:
        client = forms_client or get_forms_client()
        result = client.forms().responses().list(formId=google_form_id).execute()
        return result.get("responses", [])
    except GoogleFormsNotConfigured:
        raise
    except Exception as e:
        logger.error(
            "FORM_RESPONSE_FETCH_FAILED google_form_id=%s "
            "error_type=%s error=%s",
            google_form_id,
            type(e).__name__,
            str(e),
        )
        raise GoogleFormsAPIError(
            "Could not fetch form responses from Google. Please try again later."
        ) from e
