"""
Orchestrates ADMIN/SCHEDULER -> SYNC GOOGLE FORM RESPONSES.

Ties together google_forms_service.fetch_responses() (network),
registration_response_parser.parse_response() (pure), and
registration_sync.sync_submission() (DB transaction) - each already
independently testable, none of them aware of the others.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.database.models import FormStatus, RegistrationForm, RegistrationSubmission, SubmissionStatus
from app.services import google_forms_service, registration_sync
from app.services.audit import log_action
from app.services.google_forms_service import GoogleFormsAPIError
from app.services.registration_response_parser import ResponseValidationError, parse_response

logger = logging.getLogger("coresight.registration_sync_orchestrator")


def _parse_timestamp(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _record_rejected(db: Session, form: RegistrationForm, google_response_id: str, response: dict, reason: str) -> None:
    """A response that fails validation before sync_submission would even run (e.g. no field_mapping stored)."""
    existing = db.query(RegistrationSubmission).filter(RegistrationSubmission.google_response_id == google_response_id).first()
    if existing:
        # google_response_id is unique DB-wide, not per-form - if another
        # form already recorded this response (SYNCED/REJECTED/DUPLICATE or
        # otherwise), never insert a second row for it here.
        return
    submission = RegistrationSubmission(
        form_id=form.id, google_response_id=google_response_id,
        submitted_at=_parse_timestamp(response.get("lastSubmittedTime")) or utcnow(),
        raw_response=response,
        status=SubmissionStatus.REJECTED,
        error_message=reason,
    )
    db.add(submission)
    try:
        db.commit()
    except Exception:
        db.rollback()
        return
    log_action(db, user_id=None, action="REGISTRATION_REJECTED", entity_type="registration_submission", entity_id=str(submission.id),
               metadata={"reason": reason, "google_response_id": google_response_id})
    db.commit()


def sync_form(db: Session, form: RegistrationForm, *, triggered_by: uuid.UUID | None = None, forms_client=None) -> dict:
    """
    Syncs one form. Never raises for expected per-response outcomes
    (rejected/duplicate/failed responses are recorded, not thrown) - only
    raises if fetch_responses() itself fails (Google API/network error), so
    a caller iterating multiple forms can catch that per-form and keep
    going (see sync_all_active_forms).
    """
    summary = {"form_id": str(form.id), "responses_found": 0, "synced": 0, "duplicates": 0, "rejected": 0, "failed": 0, "skipped": 0}

    responses = google_forms_service.fetch_responses(form.google_form_id, forms_client=forms_client)
    summary["responses_found"] = len(responses)

    for response in responses:
        google_response_id = response.get("responseId")
        if not google_response_id:
            continue

        try:
            raw = parse_response(response, form.field_mapping or {})
        except ResponseValidationError as e:
            _record_rejected(db, form, google_response_id, response, str(e))
            summary["rejected"] += 1
            continue

        # Skip already-terminal responses without even calling
        # sync_submission - avoids reprocessing the entire response history
        # on every run (spec requirement) and keeps summary counts accurate
        # ("synced" means newly synced THIS run, not "is currently synced").
        existing = db.query(RegistrationSubmission).filter(RegistrationSubmission.google_response_id == google_response_id).first()
        if existing and existing.status in (SubmissionStatus.SYNCED, SubmissionStatus.REJECTED, SubmissionStatus.DUPLICATE):
            summary["skipped"] += 1
            continue

        submitted_at = _parse_timestamp(response.get("lastSubmittedTime")) or utcnow()
        submission = registration_sync.sync_submission(db, form, google_response_id, submitted_at, raw)

        if submission.status == SubmissionStatus.SYNCED:
            summary["synced"] += 1
        elif submission.status == SubmissionStatus.DUPLICATE:
            summary["duplicates"] += 1
        elif submission.status == SubmissionStatus.REJECTED:
            summary["rejected"] += 1
        elif submission.status == SubmissionStatus.FAILED:
            summary["failed"] += 1
        else:
            summary["skipped"] += 1

    form.last_synced_at = utcnow()
    db.commit()

    if triggered_by:
        log_action(
            db, user_id=triggered_by, action="REGISTRATION_SYNC_STARTED", entity_type="registration_form", entity_id=str(form.id),
            metadata={"batch_id": str(form.batch_id), **{k: v for k, v in summary.items() if k != "form_id"}},
        )
        db.commit()

    return summary


def sync_all_active_forms(db: Session, *, triggered_by: uuid.UUID | None = None) -> dict:
    """
    Syncs every ACTIVE registration form. One form's Google API failure is
    logged and skipped - it never stops the others (spec requirement).
    """
    forms = db.query(RegistrationForm).filter(RegistrationForm.status == FormStatus.ACTIVE).all()
    totals = {"forms_checked": 0, "responses_found": 0, "synced": 0, "duplicates": 0, "rejected": 0, "failed": 0, "forms_with_errors": 0}

    for form in forms:
        totals["forms_checked"] += 1
        try:
            result = sync_form(db, form, triggered_by=triggered_by)
            for key in ("responses_found", "synced", "duplicates", "rejected", "failed"):
                totals[key] += result[key]
        except GoogleFormsAPIError as e:
            logger.error("REGISTRATION_SYNC_FAILED form_id=%s reason=%s", form.id, e)
            totals["forms_with_errors"] += 1
            log_action(db, user_id=triggered_by, action="REGISTRATION_SYNC_FAILED", entity_type="registration_form", entity_id=str(form.id),
                       metadata={"batch_id": str(form.batch_id)})
            db.commit()
            continue

    return totals
