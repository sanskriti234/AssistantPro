from app.core.security import hash_password
from app.database.models import Faculty, Role, Student, StudentEnrollment, EnrollmentStatus, User


def _login(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_student_cannot_start_attendance_session(client, db_session, make_user):
    make_user("stu-noattend@coresight.edu", Role.STUDENT, password="pw")
    token = _login(client, "stu-noattend@coresight.edu", "pw")
    resp = client.post("/api/attendance/sessions/start", json={"batchId": "00000000-0000-0000-0000-000000000000", "subject": "X"}, headers=_auth(token))
    assert resp.status_code == 403


def test_student_cannot_access_admin_settings(client, make_user):
    make_user("stu-noadmin@coresight.edu", Role.STUDENT, password="pw")
    token = _login(client, "stu-noadmin@coresight.edu", "pw")
    resp = client.get("/api/settings", headers=_auth(token))
    assert resp.status_code == 403


def test_faculty_cannot_access_admin_settings(client, make_user):
    make_user("fac-noadmin@coresight.edu", Role.FACULTY, password="pw")
    token = _login(client, "fac-noadmin@coresight.edu", "pw")
    resp = client.get("/api/settings", headers=_auth(token))
    assert resp.status_code == 403


def test_unauthenticated_request_rejected(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 401


def test_faculty_cannot_start_attendance_for_unassigned_batch(client, db_session, make_user):
    from tests.test_auth_and_constraints import _make_academic_scaffold

    batch = _make_academic_scaffold(db_session)
    user = User(email="fac-unassigned@coresight.edu", password_hash=hash_password("pw"), role=Role.FACULTY)
    db_session.add(user)
    db_session.flush()
    db_session.add(Faculty(user_id=user.id, employee_id="EMP-UNASSIGNED", name="Unassigned Fac"))
    db_session.commit()

    token = _login(client, "fac-unassigned@coresight.edu", "pw")
    resp = client.post(
        "/api/attendance/sessions/start",
        json={"batchId": str(batch.id), "subject": "ML"},
        headers=_auth(token),
    )
    assert resp.status_code == 403


def test_admin_can_access_admin_dashboard(client, make_user):
    make_user("admin-ok@coresight.edu", Role.ADMIN, password="pw")
    token = _login(client, "admin-ok@coresight.edu", "pw")
    resp = client.get("/api/dashboard/admin", headers=_auth(token))
    assert resp.status_code == 200
    assert "stats" in resp.json()
