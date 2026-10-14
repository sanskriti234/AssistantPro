"""
Development-only seed data for CoreSight.

Creates: 1 admin, 2 faculty, 1 academic session, 1 course, 2 departments,
2 batches, faculty-batch assignments, 5 students enrolled in one batch
(3 with completed face enrollment status, no real embeddings - biometric
data is never fabricated), and default system settings.

Run with: python -m app.seed
"""

from app.core.security import hash_password
from app.database.base import utcnow
from app.database.connection import SessionLocal
from app.database.models import (
    Admin,
    Batch,
    Course,
    Department,
    AcademicSession,
    EnrollmentStatus,
    Faculty,
    FaceEnrollment,
    FaceEnrollmentStatus,
    FacultyBatch,
    Role,
    SessionStatus,
    Student,
    StudentContact,
    ContactType,
    StudentEnrollment,
    SystemSettings,
    User,
)


def run():
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == "admin@coresight.edu").first():
            print("Seed data already present - skipping.")
            return

        admin_user = User(email="admin@coresight.edu", password_hash=hash_password("admin"), role=Role.ADMIN)
        db.add(admin_user)
        db.flush()
        db.add(Admin(user_id=admin_user.id, name="Rhea Kapoor"))

        dept_aiml = Department(code="CSEAIML", name="CSE (AIML)")
        dept_cse = Department(code="CSE", name="CSE")
        db.add_all([dept_aiml, dept_cse])
        db.flush()

        course = Course(code="CSEAIML2027", name="CSE AIML 2027", duration_years=4)
        db.add(course)
        db.flush()

        session = AcademicSession(name="2026-27", status=SessionStatus.ACTIVE)
        db.add(session)
        db.flush()

        batch1 = Batch(academic_session_id=session.id, course_id=course.id, department_id=dept_aiml.id, year=3, section="A", name="CSE AIML 2027")
        batch2 = Batch(academic_session_id=session.id, course_id=course.id, department_id=dept_cse.id, year=3, section="B", name="CSE Core 2027")
        db.add_all([batch1, batch2])
        db.flush()

        faculty_user = User(email="faculty@coresight.edu", password_hash=hash_password("faculty"), role=Role.FACULTY)
        db.add(faculty_user)
        db.flush()
        faculty = Faculty(user_id=faculty_user.id, employee_id="EMP-001", name="Dr. Anil Verma", department_id=dept_aiml.id)
        db.add(faculty)
        db.flush()
        db.add_all([
            FacultyBatch(faculty_id=faculty.user_id, batch_id=batch1.id),
            FacultyBatch(faculty_id=faculty.user_id, batch_id=batch2.id),
        ])

        faculty2_user = User(email="meena@coresight.edu", password_hash=hash_password("faculty"), role=Role.FACULTY)
        db.add(faculty2_user)
        db.flush()
        faculty2 = Faculty(user_id=faculty2_user.id, employee_id="EMP-002", name="Prof. Meena Iyer", department_id=dept_cse.id)
        db.add(faculty2)

        students_data = [
            ("student@coresight.edu", "230001", "Sanskriti Mishra", True),
            ("arjun@coresight.edu", "230002", "Arjun Nair", True),
            ("devika@coresight.edu", "230003", "Devika Rao", False),
            ("kabir@coresight.edu", "230004", "Kabir Sethi", True),
            ("meher@coresight.edu", "230005", "Meher Chawla", True),
        ]
        for email, roll, name, enrolled in students_data:
            u = User(email=email, password_hash=hash_password("student"), role=Role.STUDENT)
            db.add(u)
            db.flush()
            s = Student(user_id=u.id, roll_number=roll, full_name=name)
            db.add(s)
            db.flush()
            db.add(StudentEnrollment(student_id=s.user_id, batch_id=batch1.id, enrollment_status=EnrollmentStatus.ACTIVE))
            db.add(StudentContact(student_id=s.user_id, contact_type=ContactType.STUDENT, name=name, mobile_number="9800000000", is_primary=True))
            if enrolled:
                # Status only - no fabricated embeddings, per project policy on
                # synthetic biometric data.
                db.add(FaceEnrollment(
                    student_id=s.user_id, status=FaceEnrollmentStatus.COMPLETE,
                    samples_processed=20, valid_samples=18, enrolled_at=utcnow(),
                ))

        db.add(SystemSettings())

        db.commit()
        print("Seed data created.")
        print("Login: admin@coresight.edu/admin, faculty@coresight.edu/faculty, student@coresight.edu/student")
    finally:
        db.close()


if __name__ == "__main__":
    run()
