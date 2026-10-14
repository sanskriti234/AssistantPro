import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database.connection import get_db
from app.database.models import RegistrationForm, Role, User
from app.schemas.schemas import RegistrationSubmissionIn
from app.services import registration_sync, registration_sync_orchestrator
from app.services.google_forms_service import GoogleFormsAPIError, GoogleFormsNotConfigured

router = APIRouter(prefix="/registration", tags=["registration"])


@router.post("/forms/{form_id}/submissions")
def submit_registration(
    form_id: uuid.UUID,
    body: RegistrationSubmissionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN)),
):
    """
    Accepts one already-normalized response directly (bypassing a live
    Google API call) - useful for testing, or for a webhook-style
    integration that pushes rows instead of CoreSight polling for them.
    For the live-polling path, see POST /registration/sync and
    POST /registration/forms/{id}/sync below.
    """
    form = db.get(RegistrationForm, form_id)
    if form is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registration form not found")
    submission = registration_sync.sync_submission(
        db, form, body.google_response_id, body.submitted_at, body.raw_response
    )
    return {"id": str(submission.id), "status": submission.status.value.lower()}


def _summary_to_camel(summary: dict) -> dict:
    mapping = {
        "forms_checked": "formsChecked",
        "responses_found": "responsesFound",
        "synced": "synced",
        "duplicates": "duplicates",
        "rejected": "rejected",
        "failed": "failed",
        "forms_with_errors": "formsWithErrors",
        "form_id": "formId",
        "skipped": "skipped",
    }
    return {mapping.get(k, k): v for k, v in summary.items()}


@router.post("/sync")
def sync_all(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN))):
    """
    Fetches and processes new responses across every ACTIVE registration
    form via the live Google Forms API. Safe to call repeatedly - already
    SYNCED/REJECTED/DUPLICATE responses are never reprocessed.
    """
    try:
        summary = registration_sync_orchestrator.sync_all_active_forms(db, triggered_by=user.id)
        return _summary_to_camel(summary)
    except GoogleFormsNotConfigured as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))


@router.post("/forms/{registration_form_id}/sync")
def sync_one_form(registration_form_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN))):
    """Syncs a single form - useful for debugging/admin operations without waiting for the scheduled sync."""
    form = db.get(RegistrationForm, registration_form_id)
    if form is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registration form not found")
    try:
        summary = registration_sync_orchestrator.sync_form(db, form, triggered_by=user.id)
        return _summary_to_camel(summary)
    except GoogleFormsNotConfigured as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))
    except GoogleFormsAPIError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))
