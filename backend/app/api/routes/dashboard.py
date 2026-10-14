import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database.connection import get_db
from app.database.models import (
    AttendanceSession,
    AttendanceSessionStatus,
    FacultyBatch,
    Role,
    Student,
    User,
)
from app.schemas.schemas import BatchOut, ClassSlotOut, DashboardStatsOut, StudentRecordOut, TrendPointOut
from app.services import academic_service, analytics_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/admin")
def admin_dashboard(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN))):
    from app.database.models import Batch

    batches = db.query(Batch).all()
    return {
        "stats": analytics_service.dashboard_stats(db),
        "trend": analytics_service.attendance_trend(db),
        "batches": [academic_service.batch_to_dict(db, b) for b in batches],
    }


@router.get("/faculty")
def faculty_dashboard(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.FACULTY))):
    links = db.query(FacultyBatch).filter(FacultyBatch.faculty_id == user.id).all()
    active_session_batch_ids = {
        s.batch_id for s in db.query(AttendanceSession).filter(
            AttendanceSession.faculty_id == user.id, AttendanceSession.status == AttendanceSessionStatus.ACTIVE
        ).all()
    }
    slots = []
    for link in links:
        batch = link.batch
        slots.append({
            "id": f"cl-{batch.id}",
            "batchId": str(batch.id),
            "batchName": batch.name,
            "section": batch.section,
            "subject": "",
            "time": "",
            "status": "active" if batch.id in active_session_batch_ids else "upcoming",
        })
    return {"classSlots": slots}


@router.get("/student", response_model=StudentRecordOut)
def student_dashboard(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.STUDENT))):
    student = db.get(Student, user.id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student profile not found")
    enrollment = next((e for e in student.enrollments if e.enrollment_status.value == "ACTIVE"), None)
    fe = student.face_enrollment
    return {
        "id": str(student.user_id),
        "name": student.full_name,
        "rollNumber": student.roll_number,
        "department": enrollment.batch.department.name if enrollment else "",
        "batchId": str(enrollment.batch_id) if enrollment else "",
        "section": enrollment.batch.section if enrollment else "",
        "email": user.email,
        "phone": next((c.mobile_number for c in student.contacts if c.contact_type.value == "STUDENT"), ""),
        "faceEnrolled": bool(fe and fe.status.value == "COMPLETE"),
        "overallAttendancePct": academic_service.overall_attendance_pct(db, student.user_id),
    }
