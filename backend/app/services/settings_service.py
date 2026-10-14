import uuid

from sqlalchemy.orm import Session

from app.database.models import SystemSettings
from app.services.audit import log_action


def get_settings_row(db: Session) -> SystemSettings:
    row = db.query(SystemSettings).order_by(SystemSettings.updated_at.desc()).first()
    if row is None:
        row = SystemSettings()
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def settings_to_dict(row: SystemSettings) -> dict:
    return {
        "recognitionThreshold": float(row.recognition_threshold),
        "livenessThreshold": float(row.liveness_threshold),
        "faceQualityThreshold": float(row.quality_threshold),
        "attendanceCooldownSeconds": row.attendance_cooldown_seconds,
        "cameraResolution": row.camera_resolution,
    }


def update_settings(db: Session, updated_by: uuid.UUID, **fields) -> SystemSettings:
    row = get_settings_row(db)
    mapping = {
        "recognitionThreshold": "recognition_threshold",
        "livenessThreshold": "liveness_threshold",
        "faceQualityThreshold": "quality_threshold",
        "attendanceCooldownSeconds": "attendance_cooldown_seconds",
        "cameraResolution": "camera_resolution",
    }
    for key, value in fields.items():
        if value is None:
            continue
        column = mapping.get(key)
        if column:
            setattr(row, column, value)
    row.updated_by = updated_by
    db.commit()
    db.refresh(row)
    log_action(db, user_id=updated_by, action="SETTINGS_UPDATED", entity_type="system_settings", entity_id=str(row.id))
    db.commit()
    return row
