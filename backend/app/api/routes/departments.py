from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Department

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("")
def list_departments(db: Session = Depends(get_db)):
    departments = (
        db.query(Department)
        .order_by(Department.code.asc())
        .all()
    )

    return [
        {
            "id": str(department.id),
            "code": department.code,
            "name": department.name,
        }
        for department in departments
    ]