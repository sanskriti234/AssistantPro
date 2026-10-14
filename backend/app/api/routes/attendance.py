import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database.connection import get_db
from app.database.models import AttendanceSession, Role, User
from app.schemas.schemas import (
    AttendanceRecordOut,
    AttendanceSessionOut,
    RecognitionResultOut,
    StartSessionRequest,
    SubmitFrameRequest,
)
from app.services import attendance_service

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/sessions/start", response_model=AttendanceSessionOut)
def start_session(body: StartSessionRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.FACULTY))):
    session = attendance_service.start_session(db, user.id, uuid.UUID(body.batchId), body.subject)
    return attendance_service.session_to_dict(db, session)


@router.post("/sessions/{session_id}/end", response_model=AttendanceSessionOut)
def end_session(session_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.FACULTY))):
    session = attendance_service.end_session(db, session_id, user.id)
    return attendance_service.session_to_dict(db, session)


@router.post("/frame", response_model=RecognitionResultOut)
def submit_frame(body: SubmitFrameRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.FACULTY))):
    from fastapi import HTTPException, status
    from app.services.face_pipeline_service import PipelineUnavailable

    session = db.get(AttendanceSession, uuid.UUID(body.sessionId))
    if session and session.faculty_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your session")
    try:
        return attendance_service.submit_frame(db, uuid.UUID(body.sessionId), body.frame)
    except PipelineUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Face recognition is unavailable: {e}")


@router.get("/history", response_model=list[AttendanceRecordOut])
def history(
    batch_id: uuid.UUID | None = None,
    date: str | None = None,
    subject: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.FACULTY)),
):
    if user.role == Role.FACULTY and batch_id:
        attendance_service.assert_faculty_assigned(db, user.id, batch_id)
    return attendance_service.attendance_history(db, batch_id=batch_id, date_str=date, subject_name=subject)


@router.get("/my-history", response_model=list[AttendanceRecordOut])
def my_history(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.STUDENT))):
    return attendance_service.student_attendance_history(db, user.id)
