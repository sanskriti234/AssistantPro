import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.pool import StaticPool

# SQLite type mappings for dialect compatibility in test environments
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

try:
    from pgvector.sqlalchemy import Vector

    @compiles(Vector, "sqlite")
    def _compile_vector_sqlite(type_, compiler, **kw):
        return "TEXT"
except ImportError:
    pass

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/coresight_test")

from app.core.security import hash_password
from app.database import connection as db_connection
from app.database.models import Base, Role, User, Admin, Faculty, Student
from app.main import app


TEST_DB_URL = os.environ["DATABASE_URL"]
ADMIN_DB_URL = TEST_DB_URL.replace("/coresight_test", "/postgres")

_GLOBAL_TEST_ENGINE = None


@pytest.fixture(scope="session", autouse=True)
def _create_test_database():
    global _GLOBAL_TEST_ENGINE
    is_postgres = False
    try:
        admin_engine = create_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            conn.execute(text("DROP DATABASE IF EXISTS coresight_test"))
            conn.execute(text("CREATE DATABASE coresight_test"))
        admin_engine.dispose()

        pg_engine = create_engine(TEST_DB_URL)
        with pg_engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        Base.metadata.create_all(pg_engine)
        _GLOBAL_TEST_ENGINE = pg_engine
        is_postgres = True
    except Exception:
        # Fall back to in-memory SQLite when PostgreSQL is unavailable
        sqlite_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(sqlite_engine)
        _GLOBAL_TEST_ENGINE = sqlite_engine

    yield

    if is_postgres and _GLOBAL_TEST_ENGINE is not None:
        _GLOBAL_TEST_ENGINE.dispose()


@pytest.fixture
def db_session():
    engine = _GLOBAL_TEST_ENGINE
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[db_connection.get_db] = override_get_db
    yield session
    session.rollback()
    session.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client(db_session):
    return TestClient(app)


@pytest.fixture
def make_user(db_session):
    def _make(email: str, role: Role, password: str = "password123"):
        user = User(email=email, password_hash=hash_password(password), role=role)
        db_session.add(user)
        db_session.flush()
        if role == Role.ADMIN:
            db_session.add(Admin(user_id=user.id, name=email.split("@")[0]))
        db_session.commit()
        return user
    return _make


from app.database.models import (
    AcademicSession,
    Course,
    Department,
    Batch,
    RegistrationForm,
    FormStatus,
)


@pytest.fixture
def test_batch(db_session):
    session = AcademicSession(
        name="TEST_SESSION_2026",
    )

    course = Course(
        code="TEST_CSE",
        name="Test Computer Science",
        duration_years=4,
    )

    department = Department(
        code="TEST_DEPT",
        name="Test Department",
    )

    db_session.add_all([session, course, department])
    db_session.flush()

    batch = Batch(
        academic_session_id=session.id,
        course_id=course.id,
        department_id=department.id,
        year=1,
        section="A",
        name="Test Batch",
    )

    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    return batch


@pytest.fixture
def test_registration_form(db_session, test_batch, make_user):
    admin = make_user(
        email="test.registration.admin@coresight.test",
        role=Role.ADMIN,
    )

    form = RegistrationForm(
        batch_id=test_batch.id,
        google_form_id="TEST_GOOGLE_FORM_ID",
        form_url="https://example.com/test-form",
        status=FormStatus.ACTIVE,
        created_by=admin.id,
    )

    db_session.add(form)
    db_session.commit()
    db_session.refresh(form)

    return form