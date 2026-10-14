import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database.connection import get_db
from app.database.models import FacultyBatch, Role, User
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/institution")
def institution_analytics(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN))):
    return {
        "trend": analytics_service.attendance_trend(db),
        "byDepartment": analytics_service.department_attendance(db),
        "byBatch": analytics_service.batch_attendance(db),
        "recognitionSuccessPct": analytics_service.recognition_success_pct(db),
        "spoofAttempts": analytics_service.spoof_attempts_total(db),
    }


@router.get("/faculty")
def faculty_analytics(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.FACULTY))):
    batch_ids = [l.batch_id for l in db.query(FacultyBatch).filter(FacultyBatch.faculty_id == user.id).all()]
    return {
        "trend": analytics_service.attendance_trend(db),
        "byBatch": analytics_service.batch_attendance(db, batch_ids),
    }
