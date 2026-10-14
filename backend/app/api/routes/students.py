from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database.connection import get_db
from app.database.models import Role, Student, User
from app.schemas.schemas import StudentRecordOut
from app.services import academic_service

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/me", response_model=StudentRecordOut)
def my_profile(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.STUDENT))):
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
