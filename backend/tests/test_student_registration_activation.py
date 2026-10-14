from unittest.mock import patch
from app.services.registration_sync import sync_submission
from app.database.models import (
    User,
    Student,
    StudentEnrollment,
    RegistrationForm,
    RegistrationSubmission,
    Role,
    EnrollmentStatus,
    SubmissionStatus,
)
from datetime import datetime, timezone
def test_new_student_gets_student_activation_email(
    db_session,
    test_batch,
    test_registration_form,
):
    """
    Test student registration without actually filling Google Form.

    Expected:
    - New User is created as inactive
    - New Student is created
    - Student is enrolled in the form's batch
    - Student activation token is created
    - Student activation email is sent
    - Faculty activation email is NOT sent
    """

    google_response_id = "TEST_RESPONSE_001"

    raw_response = {
        "name": "Test Student",
        "roll_number": "TEST001",
        "gender": "Female",
        "date_of_birth": "2004-12-23",
        "email": "test.student@coresight.test",
        "student_mobile": "9876543210",
        "father_name": "Test Father",
        "mother_name": "Test Mother",
        "address": "Test Address",
        "high_school_board": "CBSE",
        "high_school_institution": "Test School",
        "high_school_passing_year": "2021",
        "high_school_score": "85",
        "intermediate_board": "CBSE",
        "intermediate_institution": "Test School",
        "intermediate_passing_year": "2023",
        "intermediate_score": "88",
        "batch_confirmation": "Yes",
    }

    with patch(
        "app.services.registration_sync.activation_service.send_student_activation_email"
    ) as mock_student_email, patch(
        "app.services.registration_sync.activation_service.send_activation_email"
    ) as mock_faculty_email:

        result = sync_submission(
            db=db_session,
            form=test_registration_form,
            google_response_id=google_response_id,
            submitted_at=datetime.now(timezone.utc),
            raw=raw_response,
        )

    # ---------------------------------------
    # 1. User should be created
    # ---------------------------------------

    user = (
        db_session.query(User)
        .filter(User.email == "test.student@coresight.test")
        .first()
    )

    assert user is not None

    # ---------------------------------------
    # 2. User must initially be inactive
    # ---------------------------------------

    assert user.is_active is False
    assert user.role == Role.STUDENT

    # ---------------------------------------
    # 3. Student should be created
    # ---------------------------------------

    student = (
        db_session.query(Student)
        .filter(Student.user_id == user.id)
        .first()
    )

    assert student is not None
    assert student.roll_number == "TEST001"
    assert student.full_name == "Test Student"

    # ---------------------------------------
    # 4. Student must belong to form batch
    # ---------------------------------------

    enrollment = (
        db_session.query(StudentEnrollment)
        .filter(
            StudentEnrollment.student_id == student.user_id,
            StudentEnrollment.batch_id == test_registration_form.batch_id,
        )
        .first()
    )

    assert enrollment is not None
    assert enrollment.enrollment_status == EnrollmentStatus.ACTIVE

    # ---------------------------------------
    # 5. Submission should be synced
    # ---------------------------------------

    submission = (
        db_session.query(RegistrationSubmission)
        .filter(
            RegistrationSubmission.google_response_id
            == google_response_id
        )
        .first()
    )

    assert submission is not None
    assert submission.status == SubmissionStatus.SYNCED
    assert submission.student_id == student.user_id

    # ---------------------------------------
    # 6. STUDENT activation email sent
    # ---------------------------------------

    mock_student_email.assert_called_once()

    email_call = mock_student_email.call_args

    assert email_call.kwargs["user"] == user
    assert email_call.kwargs["student_name"] == "Test Student"
    assert (
        email_call.kwargs["batch_name"]
        == test_registration_form.batch.name
    )

    # ---------------------------------------
    # 7. FACULTY activation email NOT sent
    # ---------------------------------------

    mock_faculty_email.assert_not_called()