import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password, verify_password
from app.database.models import (
    AcademicSession,
    AttendanceRecord,
    AttendanceSession,
    AttendanceSessionStatus,
    AttendanceStatus,
    Batch,
    Course,
    Department,
    Faculty,
    FacultyBatch,
    Role,
    SessionStatus,
    Student,
    StudentEnrollment,
    EnrollmentStatus,
    User,
)


def test_password_hashing_roundtrip():
    h = hash_password("correct-horse")
    assert verify_password("correct-horse", h)
    assert not verify_password("wrong", h)


def test_user_creation_and_unique_email(db_session, make_user):
    make_user("dup@coresight.edu", Role.ADMIN)
    with pytest.raises(IntegrityError):
        make_user("dup@coresight.edu", Role.ADMIN)
    db_session.rollback()


def test_login_rejects_wrong_password(client, make_user):
    make_user("someone@coresight.edu", Role.ADMIN, password="right-pass")
    resp = client.post("/api/auth/login", json={"email": "someone@coresight.edu", "password": "wrong"})
    assert resp.status_code == 401


def test_login_succeeds_and_returns_role(client, make_user):
    make_user("someone2@coresight.edu", Role.ADMIN, password="right-pass")
    resp = client.post("/api/auth/login", json={"email": "someone2@coresight.edu", "password": "right-pass"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["role"] == "admin"
    assert "accessToken" in body


def _make_academic_scaffold(db_session):
    suffix = uuid.uuid4().hex[:8]
    dept = Department(code=f"TST{suffix}", name=f"Test Dept {suffix}")
    course = Course(code=f"TSTC{suffix}", name=f"Test Course {suffix}", duration_years=4)
    db_session.add_all([dept, course])
    db_session.flush()
    session = AcademicSession(name=f"2099-{suffix}", status=SessionStatus.ACTIVE)
    db_session.add(session)
    db_session.flush()
    batch = Batch(academic_session_id=session.id, course_id=course.id, department_id=dept.id, year=1, section="A", name=f"Test Batch {suffix}")
    db_session.add(batch)
    db_session.flush()
    return batch


def test_duplicate_batch_identity_rejected(db_session):
    dept = Department(code="DUP", name="Dup Dept")
    course = Course(code="DUPC", name="Dup Course", duration_years=4)
    db_session.add_all([dept, course])
    db_session.flush()
    session = AcademicSession(name="dup-session", status=SessionStatus.ACTIVE)
    db_session.add(session)
    db_session.flush()

    b1 = Batch(academic_session_id=session.id, course_id=course.id, department_id=dept.id, year=1, section="A", name="B1")
    db_session.add(b1)
    db_session.commit()

    b2 = Batch(academic_session_id=session.id, course_id=course.id, department_id=dept.id, year=1, section="A", name="B2")
    db_session.add(b2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicate_roll_number_rejected(db_session):
    u1 = User(email="s1@coresight.edu", password_hash=hash_password("x"), role=Role.STUDENT)
    u2 = User(email="s2@coresight.edu", password_hash=hash_password("x"), role=Role.STUDENT)
    db_session.add_all([u1, u2])
    db_session.flush()
    db_session.add(Student(user_id=u1.id, roll_number="RN-DUP", full_name="A"))
    db_session.commit()
    db_session.add(Student(user_id=u2.id, roll_number="RN-DUP", full_name="B"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicate_faculty_batch_assignment_rejected(db_session):
    batch = _make_academic_scaffold(db_session)
    u = User(email="fac@coresight.edu", password_hash=hash_password("x"), role=Role.FACULTY)
    db_session.add(u)
    db_session.flush()
    fac = Faculty(user_id=u.id, employee_id="EMP-DUP", name="Fac")
    db_session.add(fac)
    db_session.commit()

    db_session.add(FacultyBatch(faculty_id=fac.user_id, batch_id=batch.id))
    db_session.commit()
    db_session.add(FacultyBatch(faculty_id=fac.user_id, batch_id=batch.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicate_attendance_rejected_at_db_level(db_session):
    batch = _make_academic_scaffold(db_session)
    fac_user = User(email=f"fac2-{uuid.uuid4().hex[:8]}@coresight.edu", password_hash=hash_password("x"), role=Role.FACULTY)
    db_session.add(fac_user)
    db_session.flush()
    fac = Faculty(user_id=fac_user.id, employee_id=f"EMP-ATT-{uuid.uuid4().hex[:8]}", name="Fac2")
    db_session.add(fac)

    stu_user = User(email=f"stu-{uuid.uuid4().hex[:8]}@coresight.edu", password_hash=hash_password("x"), role=Role.STUDENT)
    db_session.add(stu_user)
    db_session.flush()
    student = Student(user_id=stu_user.id, roll_number=f"RN-ATT-{uuid.uuid4().hex[:8]}", full_name="Stu")
    db_session.add(student)
    db_session.commit()

    att_session = AttendanceSession(batch_id=batch.id, faculty_id=fac.user_id, status=AttendanceSessionStatus.ACTIVE)
    db_session.add(att_session)
    db_session.commit()

    r1 = AttendanceRecord(attendance_session_id=att_session.id, student_id=student.user_id, status=AttendanceStatus.PRESENT)
    db_session.add(r1)
    db_session.commit()

    r2 = AttendanceRecord(attendance_session_id=att_session.id, student_id=student.user_id, status=AttendanceStatus.PRESENT)
    db_session.add(r2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
