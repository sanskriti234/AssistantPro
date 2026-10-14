from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database.connection import get_db
from app.database.models import Role, User
from app.schemas.schemas import SystemSettingsOut, SystemSettingsUpdate
from app.services import settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SystemSettingsOut)
def get_settings(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN))):
    return settings_service.settings_to_dict(settings_service.get_settings_row(db))


@router.put("", response_model=SystemSettingsOut)
def update_settings(body: SystemSettingsUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN))):
    row = settings_service.update_settings(db, user.id, **body.model_dump())
    return settings_service.settings_to_dict(row)
