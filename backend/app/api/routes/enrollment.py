from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database.connection import get_db
from app.database.models import Role, User
from app.schemas.schemas import (
    FinalizeEnrollmentRequest,
    ValidateSampleRequest,
    ValidateSampleResponse,
    EnrollmentResultOut,
)
from app.services import enrollment_service
from app.services.face_pipeline_service import PipelineUnavailable

router = APIRouter(prefix="/enrollment", tags=["enrollment"])


@router.post("/validate-sample", response_model=ValidateSampleResponse)
def validate_sample(body: ValidateSampleRequest, user: User = Depends(require_roles(Role.STUDENT))):
    try:
        accepted, reason = enrollment_service.validate_sample(body.frame, user.id)
    except PipelineUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Face recognition is unavailable: {e}")
    return {"accepted": accepted, "reason": reason}


@router.post("/finalize", response_model=EnrollmentResultOut)
def finalize(body: FinalizeEnrollmentRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.STUDENT))):
    return enrollment_service.finalize_enrollment(db, user.id, body.validSampleCount, body.embeddings)
