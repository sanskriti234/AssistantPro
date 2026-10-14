import uuid

from sqlalchemy.orm import Session

from app.database.models import AuditLog


def log_action(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """
    Append an audit row. Does not commit - callers own the transaction
    boundary so this can participate in the same commit as the action it
    records. Never pass secrets or raw biometric embeddings in metadata.
    """
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
        )
    )
