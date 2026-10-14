from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database.connection import get_db
from app.database.models import Faculty, FacultyBatch, Role, User
from app.schemas.schemas import (
    AcademicSessionOut,
    BatchOut,
    CreateBatchRequest,
    CreateSessionRequest,
    FacultyRecordOut,
    StudentRecordOut,
)
from app.services import academic_service
from app.services.audit import log_action

router = APIRouter(tags=["batches"])


@router.get("/sessions", response_model=list[AcademicSessionOut])
def list_sessions(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN))):
    return academic_service.list_sessions(db)


@router.post("/sessions", response_model=list[AcademicSessionOut])
def create_session(body: CreateSessionRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN))):
    session = academic_service.create_session(db, body.label)
    log_action(db, user_id=user.id, action="ACADEMIC_SESSION_CREATED", entity_type="academic_session", entity_id=str(session.id))
    db.commit()
    return academic_service.list_sessions(db)


@router.post("/sessions/{session_id}/toggle", response_model=list[AcademicSessionOut])
def toggle_session(session_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN))):
    if academic_service.toggle_session(db, session_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return academic_service.list_sessions(db)


@router.get("/batches", response_model=list[BatchOut])
def list_batches(session_id: UUID | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    batches = academic_service.list_batches(db, session_id)
    return [academic_service.batch_to_dict(db, b) for b in batches]


@router.post("/batches", response_model=BatchOut)
def create_batch(body: CreateBatchRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN))):
    batch = academic_service.create_batch(
        db, name=body.name, department_name=body.department, year=body.year,
        section=body.section, session_id=UUID(body.sessionId),
    )
    log_action(db, user_id=user.id, action="ADMIN_CREATED_BATCH", entity_type="batch", entity_id=str(batch.id))
    db.commit()
    return academic_service.batch_to_dict(db, batch)


@router.get("/batches/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    batches = academic_service.list_batches(db)
    batch = next((b for b in batches if b.id == batch_id), None)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    return academic_service.batch_to_dict(db, batch)


@router.post("/batches/{batch_id}/generate-form", response_model=BatchOut)
def generate_form(batch_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN))):
    from app.database.models import Batch
    from app.services import registration_form_service
    from app.services.google_forms_service import GoogleFormsAPIError, GoogleFormsNotConfigured

    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")

    try:
        registration_form_service.generate_or_get_form(db, batch, user.id)
    except GoogleFormsNotConfigured as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))
    except GoogleFormsAPIError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))

    db.refresh(batch)
    return academic_service.batch_to_dict(db, batch)


@router.get("/batches/{batch_id}/students", response_model=list[StudentRecordOut])
def batch_students(batch_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN, Role.FACULTY))):
    if user.role == Role.FACULTY:
        academic_service_check = db.query(FacultyBatch).filter(
            FacultyBatch.faculty_id == user.id, FacultyBatch.batch_id == batch_id
        ).first()
        if academic_service_check is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not assigned to this batch")
    return academic_service.batch_students(db, batch_id)


@router.get("/faculty", response_model=list[FacultyRecordOut])
def list_faculty(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN))):
    faculty = db.query(Faculty).all()
    return [
        {
            "id": str(f.user_id),
            "name": f.name,
            "email": f.user.email,
            "assignedBatchIds": [str(link.batch_id) for link in f.batch_links],
        }
        for f in faculty
    ]


@router.get("/faculty/{faculty_id}/batches", response_model=list[BatchOut])
def faculty_batches(faculty_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == Role.FACULTY and user.id != faculty_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot view another faculty member's batches")
    links = db.query(FacultyBatch).filter(FacultyBatch.faculty_id == faculty_id).all()
    return [academic_service.batch_to_dict(db, link.batch) for link in links]

@router.delete("/admin/faculty/{faculty_id}")
def deactivate_faculty(
    faculty_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only admins can deactivate faculty access
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    faculty = db.get(Faculty, faculty_id)

    if faculty is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty not found",
        )

    # Find the User account connected to this faculty member
    user = db.query(User).filter(
        User.id == faculty.user_id
    ).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty login account not found",
        )

    # Disable portal access
    user.is_active = False

    db.commit()

    return {
        "message": "Faculty portal access has been deactivated successfully"
    }