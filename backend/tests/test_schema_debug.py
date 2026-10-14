from sqlalchemy import inspect

import tests.conftest as conftest


def test_debug_student_contact_schema():
    engine = conftest._GLOBAL_TEST_ENGINE

    assert engine is not None, "Test engine was not initialized"

    inspector = inspect(engine)

    print("\n=== STUDENT CONTACT UNIQUE CONSTRAINTS ===")
    print(inspector.get_unique_constraints("student_contacts"))

    print("\n=== STUDENT CONTACT INDEXES ===")
    print(inspector.get_indexes("student_contacts"))

    print("\n=== STUDENT CONTACT TABLE SQL ===")
    with engine.connect() as conn:
        result = conn.exec_driver_sql(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'student_contacts'
            """
        )
        print(result.scalar())