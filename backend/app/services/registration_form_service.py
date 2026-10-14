"""
Orchestrates ADMIN -> GENERATE REGISTRATION FORM.

Keeps Google API concerns (google_forms_service.py) and CoreSight
persistence/business rules (this file) separate, per project convention.
This is the only place that decides whether to call Google at all -
routes never call google_forms_service directly.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.database.models import Batch, FormStatus, RegistrationForm
from app.services import google_forms_service
from app.services.audit import log_action

logger = logging.getLogger("coresight.registration_form")


def registration_form_to_dict(form: RegistrationForm) -> dict:
    return {
        "id": str(form.id),
        "batchId": str(form.batch_id),
        "googleFormId": form.google_form_id,
        "formUrl": form.form_url,
        "status": form.status.value.lower(),
        "createdAt": form.created_at.isoformat(),
    }


def generate_or_get_form(db: Session, batch: Batch, admin_user_id: uuid.UUID) -> tuple[RegistrationForm, bool]:
    """
    Returns (form, created). If an active form already exists for this
    batch, it is returned unchanged and no Google API call is made -
    clicking "Generate Registration Form" repeatedly is always safe.
    registration_forms.batch_id is UNIQUE, so this is also enforced at the
    database level, not just here.
    """
    existing = db.query(RegistrationForm).filter(RegistrationForm.batch_id == batch.id).first()
    if existing is not None:
        logger.info("FORM_ALREADY_EXISTS batch_id=%s registration_form_id=%s", batch.id, existing.id)
        log_action(
            db, user_id=admin_user_id, action="FORM_ALREADY_EXISTS",
            entity_type="registration_form", entity_id=str(existing.id),
            metadata={"batch_id": str(batch.id)},
        )
        db.commit()
        return existing, False

    # Google API call happens BEFORE any database write, so a failure here
    # leaves no partial/invalid registration_forms row behind.
    result = google_forms_service.create_registration_form(batch)

    form = RegistrationForm(
        batch_id=batch.id,
        google_form_id=result["google_form_id"],
        google_sheet_id=None,  # see google_forms_service module docstring
        form_url=result["form_url"],
        status=FormStatus.ACTIVE,
        created_by=admin_user_id,
        field_mapping=result.get("field_mapping"),
    )
    db.add(form)
    db.flush()

    log_action(
        db, user_id=admin_user_id, action="REGISTRATION_FORM_CREATED",
        entity_type="registration_form", entity_id=str(form.id),
        metadata={"batch_id": str(batch.id), "google_form_id": result["google_form_id"]},
    )
    db.commit()
    db.refresh(form)
    return form, True
