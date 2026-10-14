"""
Converts one Google Forms API response object into the raw dict shape
registration_sync.sync_submission() expects, using the form's stored
field_mapping ({field_key: google_question_id}) - never by matching
question text, per project policy (question titles can change; questionIds
don't).

Kept separate from Google API calls (google_forms_service.py) and from
SQLAlchemy operations (registration_sync.py), per project convention.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any


class ResponseValidationError(Exception):
    """
    Raised when a response is missing a required field or contains an
    unparseable value. Callers should record this as a REJECTED submission
    (permanent - not retried) rather than FAILED (transient - retried).
    """


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

REQUIRED_FIELDS = [
    "name", "roll_number", "gender", "date_of_birth", "email", "student_mobile",
    "father_name", "mother_name", "address",
    "high_school_board", "high_school_institution", "high_school_passing_year", "high_school_score",
    "intermediate_board", "intermediate_institution", "intermediate_passing_year", "intermediate_score",
]

# Diploma fields are intentionally excluded from REQUIRED_FIELDS - an
# incomplete/blank diploma section is valid and simply produces no
# DIPLOMA qualification row (see registration_sync.py).
DIPLOMA_FIELDS = [
    "diploma_board", "diploma_institution", "diploma_course",
    "diploma_passing_year", "diploma_score", "diploma_roll_number",
]


def _extract_answer_text(response: dict[str, Any], question_id: str) -> str | None:
    """
    Forms API answers are keyed by questionId under `answers`, each holding
    a `textAnswers.answers[].value` list (single-value questions - which is
    all this form uses except the file upload - have exactly one entry).
    """
    answers = response.get("answers", {})
    entry = answers.get(question_id)
    if not entry:
        return None
    text_answers = entry.get("textAnswers", {}).get("answers", [])
    if text_answers:
        return text_answers[0].get("value", "").strip() or None
    return None


def _extract_file_id(response: dict[str, Any], question_id: str) -> str | None:
    """
    File-upload answers carry `fileUploadAnswers.answers[].fileId` (a Drive
    file ID) rather than a public URL - see storage_service.py for how this
    is turned into a CoreSight-hosted profile photo.
    """
    answers = response.get("answers", {})
    entry = answers.get(question_id)
    if not entry:
        return None
    files = entry.get("fileUploadAnswers", {}).get("answers", [])
    if files:
        return files[0].get("fileId")
    return None


def _safe_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _parse_date(value: str, field_name: str) -> date:
    from datetime import datetime as _dt

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return _dt.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ResponseValidationError(f"Could not parse {field_name} as a date: {value!r}")


def _parse_int(value: str, field_name: str) -> int:
    digits = re.sub(r"[^\d]", "", value)
    if not digits:
        raise ResponseValidationError(f"Could not parse {field_name} as a number: {value!r}")
    return int(digits)


def parse_response(response: dict[str, Any], field_mapping: dict[str, str]) -> dict[str, Any]:
    """
    Returns a raw dict compatible with registration_sync.sync_submission's
    `raw` parameter. Raises ResponseValidationError (permanent - REJECTED)
    if a required field is missing or malformed. Never raises for missing
    optional/diploma fields.
    """
    if not field_mapping:
        raise ResponseValidationError(
            "This registration form has no stored question mapping - it was "
            "likely created before response synchronization was implemented. "
            "Regenerate the form to enable synchronization."
        )

    raw: dict[str, Any] = {}
    for field_key, question_id in field_mapping.items():
        if field_key == "profile_photo_file_id":
            raw[field_key] = _extract_file_id(response, question_id)
        else:
            raw[field_key] = _extract_answer_text(response, question_id)

    missing = [f for f in REQUIRED_FIELDS if not raw.get(f)]
    if missing:
        raise ResponseValidationError(f"Missing required field(s): {', '.join(missing)}")

    if (raw.get("batch_confirmation") or "").strip().lower() not in ("yes", "y"):
        raise ResponseValidationError("Batch confirmation was not answered \u201cYes\u201d")

    if not _EMAIL_RE.match(raw["email"]):
        raise ResponseValidationError(f"Invalid email address: {raw['email']!r}")

    # Normalize.
    raw["email"] = raw["email"].strip().lower()
    raw["name"] = raw["name"].strip()
    raw["roll_number"] = raw["roll_number"].strip()
    raw["date_of_birth"] = _parse_date(raw["date_of_birth"], "date_of_birth").isoformat()

    if raw.get("semester"):
        raw["semester"] = _parse_int(raw["semester"], "semester")

    for prefix in ("high_school", "intermediate", "diploma"):
        year_key = f"{prefix}_passing_year"
        if raw.get(year_key):
            raw[year_key] = _parse_int(raw[year_key], year_key)
        score_key = f"{prefix}_score"
        if raw.get(score_key):
            numeric = _safe_float(raw[score_key])
            raw[f"{score_key}_type"] = "CGPA" if numeric is not None and numeric <= 10 else "PERCENTAGE"

    # Diploma is optional as a whole: if none of its fields were answered,
    # drop any stray Nones so registration_sync.py's `if not board: skip`
    # check behaves the same as "the section was left blank".
    if not any(raw.get(f) for f in DIPLOMA_FIELDS):
        for f in DIPLOMA_FIELDS:
            raw.pop(f, None)
        raw.pop("diploma_score_type", None)

    return raw
