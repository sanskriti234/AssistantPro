"""
CoreSight registration synchronization.

Google Form response -> normalized CoreSight records.

Rules:
- Roll number identifies the student.
- Email belongs to the student's CoreSight account.
- Only the student gets a User account.
- Father/mother/guardian are StudentContact data only.
- Father/mother/guardian NEVER get User records or activation tokens.
- Batch comes from RegistrationForm.batch_id.
- Google response ID makes synchronization idempotent.
- New student -> account + enrollment + submitted data + activation.
- Existing student -> update submitted data + ensure enrollment.
- Existing student -> no new User and no new activation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database.models import (
    ContactType,
    EnrollmentStatus,
    QualificationType,
    RegistrationForm,
    RegistrationSubmission,
    Role,
    Student,
    StudentAddress,
    StudentContact,
    StudentEnrollment,
    StudentQualification,
    SubmissionStatus,
    User,
)
from app.services import activation_service
from app.services.audit import log_action


logger = logging.getLogger("coresight.registration_sync")

_PLACEHOLDER_PASSWORD_PREFIX = "unset:"

_TERMINAL_STATUSES = {
    SubmissionStatus.SYNCED,
    SubmissionStatus.REJECTED,
    SubmissionStatus.DUPLICATE,
}


# ============================================================================
# TEMPORARY PASSWORD
# ============================================================================


def _temp_password_hash() -> str:
    """
    Create a password hash that cannot practically be used as a normal
    password.

    The student remains inactive until the activation flow sets a real
    password.
    """
    return hash_password(
        f"{_PLACEHOLDER_PASSWORD_PREFIX}{uuid.uuid4()}"
    )


# ============================================================================
# MAIN SYNC
# ============================================================================


def sync_submission(
    db: Session,
    form: RegistrationForm,
    google_response_id: str,
    submitted_at: datetime,
    raw: dict,
) -> RegistrationSubmission:
    """
    Synchronize one Google Form response into CoreSight.

    NEW STUDENT
    -----------
    Google response
        -> find by roll number
        -> no student found
        -> create STUDENT User
        -> create Student
        -> create StudentEnrollment
        -> store submitted student data
        -> store submitted family contact data as StudentContact only
        -> create activation token
        -> send student activation email

    EXISTING STUDENT
    ----------------
    Google response
        -> find by roll number
        -> reuse existing Student/User
        -> update only submitted values
        -> ensure enrollment
        -> no new User
        -> no activation token
        -> no activation email

    IMPORTANT
    ---------
    Father, mother and guardian are NOT CoreSight users.
    Their names/mobile numbers, when submitted by the student, are stored
    only as StudentContact records linked to the student's student_id.
    """

    # ----------------------------------------------------------------------
    # 1. IDEMPOTENCY
    # ----------------------------------------------------------------------

    existing_submission = (
        db.query(RegistrationSubmission)
        .filter(
            RegistrationSubmission.google_response_id
            == google_response_id
        )
        .first()
    )

    if (
        existing_submission
        and existing_submission.status in _TERMINAL_STATUSES
    ):
        return existing_submission

    submission = existing_submission or RegistrationSubmission(
        form_id=form.id,
        google_response_id=google_response_id,
        submitted_at=submitted_at,
        raw_response=raw,
        status=SubmissionStatus.PENDING,
    )

    if existing_submission is None:
        db.add(submission)

    submission.status = SubmissionStatus.PROCESSING
    submission.error_message = None

    db.flush()

    try:

        # ------------------------------------------------------------------
        # 2. REQUIRED STUDENT DATA
        # ------------------------------------------------------------------

        roll_number = raw["roll_number"].strip()
        email = raw["email"].strip().lower()
        full_name = raw["name"].strip()

        # ------------------------------------------------------------------
        # 3. STUDENT IDENTITY = ROLL NUMBER
        # ------------------------------------------------------------------

        student = (
            db.query(Student)
            .filter(
                Student.roll_number == roll_number
            )
            .first()
        )

        is_new_registration = student is None
        if student is not None:
            submission.status = SubmissionStatus.DUPLICATE
            submission.student_id = student.user_id
            submission.error_message = (
                f"Roll number {roll_number} is already registered "
                "by another Google Form response."
            )
            db.commit()
            return submission
        

        # ==================================================================
        # 4. NEW STUDENT
        # ==================================================================

        if is_new_registration:

            # --------------------------------------------------------------
            # The submitted email belongs to the student's account.
            #
            # User.email is unique, so a completely new student cannot use
            # an email already belonging to another CoreSight account.
            # --------------------------------------------------------------

            existing_user = (
                db.query(User)
                .filter(
                    User.email == email
                )
                .first()
            )

            if existing_user is not None:

                submission.status = SubmissionStatus.DUPLICATE

                submission.error_message = (
                    f"Email {email} is already associated "
                    f"with another CoreSight account and cannot be used "
                    f"for this new student."
                )

                db.commit()

                log_action(
                    db,
                    user_id=None,
                    action="REGISTRATION_DUPLICATE",
                    entity_type="registration_submission",
                    entity_id=str(submission.id),
                    metadata={
                        "reason": "email_already_registered",
                        "google_response_id": google_response_id,
                        "roll_number": roll_number,
                    },
                )

                db.commit()

                return submission

            # --------------------------------------------------------------
            # CREATE ONLY THE STUDENT USER
            # --------------------------------------------------------------

            user = User(
                email=email,
                password_hash=_temp_password_hash(),
                role=Role.STUDENT,
                is_active=False,
            )

            db.add(user)
            db.flush()

            # --------------------------------------------------------------
            # CREATE STUDENT
            # --------------------------------------------------------------

            student = Student(
                user_id=user.id,
                roll_number=roll_number,
                full_name=full_name,
                gender=raw.get("gender"),
                date_of_birth=_parse_iso_date(
                    raw.get("date_of_birth")
                ),
            )

            db.add(student)
            db.flush()

        # ==================================================================
        # 5. EXISTING STUDENT
        # ==================================================================

        else:

            # IMPORTANT:
            # Reuse the student's existing CoreSight User.
            # Do NOT create another User based on the submitted email.

            user = student.user

            # --------------------------------------------------------------
            # Update ONLY values actually submitted by the student.
            # --------------------------------------------------------------

            if raw.get("name"):
                student.full_name = full_name

            if raw.get("gender"):
                student.gender = raw["gender"]

            if raw.get("date_of_birth"):
                parsed_dob = _parse_iso_date(
                    raw["date_of_birth"]
                )

                if parsed_dob is not None:
                    student.date_of_birth = parsed_dob

        # ------------------------------------------------------------------
        # SAFETY INVARIANT
        # ------------------------------------------------------------------

        # The only User touched by registration sync is the student's User.
        # Father/mother/guardian never reach this object.

        if user.role != Role.STUDENT:
            raise ValueError(
                f"Student {roll_number} is linked to a non-student User."
            )

        # ==================================================================
        # 6. STUDENT ENROLLMENT
        # ==================================================================

        # Batch comes from the RegistrationForm.
        # The student does NOT control the batch.

        existing_enrollment = (
            db.query(StudentEnrollment)
            .filter(
                StudentEnrollment.student_id == student.user_id,
                StudentEnrollment.batch_id == form.batch_id,
            )
            .first()
        )

        if existing_enrollment is None:

            db.add(
                StudentEnrollment(
                    student_id=student.user_id,
                    batch_id=form.batch_id,
                    semester=raw.get("semester"),
                    enrollment_status=EnrollmentStatus.ACTIVE,
                )
            )

        # ==================================================================
        # 7. STUDENT CONTACT
        # ==================================================================

        _upsert_contact(
            db=db,
            student_id=student.user_id,
            contact_type=ContactType.STUDENT,
            name=full_name,
            mobile=raw.get("student_mobile"),
            is_primary=True,
        )

        # ==================================================================
        # 8. FATHER CONTACT — DATA ONLY
        # ==================================================================

        # This is NOT a User.
        # This is NOT a Student.
        # This is NOT a login account.
        # This does NOT receive an activation token.

        if raw.get("father_name") or raw.get("father_mobile"):

            _upsert_contact(
                db=db,
                student_id=student.user_id,
                contact_type=ContactType.FATHER,
                name=raw.get("father_name", ""),
                mobile=raw.get("father_mobile"),
            )

        # ==================================================================
        # 9. MOTHER CONTACT — DATA ONLY
        # ==================================================================

        if raw.get("mother_name") or raw.get("mother_mobile"):

            _upsert_contact(
                db=db,
                student_id=student.user_id,
                contact_type=ContactType.MOTHER,
                name=raw.get("mother_name", ""),
                mobile=raw.get("mother_mobile"),
            )

        # ==================================================================
        # 10. GUARDIAN CONTACT — DATA ONLY
        # ==================================================================

        # Guardian is used only when father and mother mobile numbers are
        # not available.

        if (
            raw.get("guardian_mobile")
            and not raw.get("father_mobile")
            and not raw.get("mother_mobile")
        ):

            _upsert_contact(
                db=db,
                student_id=student.user_id,
                contact_type=ContactType.GUARDIAN,
                name=raw.get("guardian_name", ""),
                mobile=raw.get("guardian_mobile"),
            )

        # ==================================================================
        # 11. ADDRESS
        # ==================================================================

        if raw.get("address"):

            address = (
                db.query(StudentAddress)
                .filter(
                    StudentAddress.student_id
                    == student.user_id
                )
                .first()
            )

            if address is None:

                db.add(
                    StudentAddress(
                        student_id=student.user_id,
                        address_line=raw["address"],
                    )
                )

            else:

                address.address_line = raw["address"]

        # ==================================================================
        # 12. QUALIFICATIONS
        # ==================================================================

        for qualification_type, prefix in (
            (
                QualificationType.HIGH_SCHOOL,
                "high_school",
            ),
            (
                QualificationType.INTERMEDIATE,
                "intermediate",
            ),
            (
                QualificationType.DIPLOMA,
                "diploma",
            ),
        ):

            board = raw.get(
                f"{prefix}_board"
            )

            # No submitted qualification.
            if not board:
                continue

            existing_qualification = (
                db.query(StudentQualification)
                .filter(
                    StudentQualification.student_id
                    == student.user_id,
                    StudentQualification.qualification_type
                    == qualification_type,
                )
                .first()
            )

            if existing_qualification is None:

                db.add(
                    StudentQualification(
                        student_id=student.user_id,
                        qualification_type=qualification_type,
                        board=board,
                        institution=raw.get(
                            f"{prefix}_institution"
                        ),
                        passing_year=raw.get(
                            f"{prefix}_passing_year"
                        ),
                        score=raw.get(
                            f"{prefix}_score"
                        ),
                        score_type=raw.get(
                            f"{prefix}_score_type"
                        ),
                        roll_number=raw.get(
                            f"{prefix}_roll_number"
                        ),
                    )
                )

            else:

                # Update only submitted values.

                existing_qualification.board = board

                if raw.get(
                    f"{prefix}_institution"
                ):
                    existing_qualification.institution = raw.get(
                        f"{prefix}_institution"
                    )

                if raw.get(
                    f"{prefix}_passing_year"
                ):
                    existing_qualification.passing_year = raw.get(
                        f"{prefix}_passing_year"
                    )

                if raw.get(
                    f"{prefix}_score"
                ):
                    existing_qualification.score = raw.get(
                        f"{prefix}_score"
                    )

                if raw.get(
                    f"{prefix}_score_type"
                ):
                    existing_qualification.score_type = raw.get(
                        f"{prefix}_score_type"
                    )

                if raw.get(
                    f"{prefix}_roll_number"
                ):
                    existing_qualification.roll_number = raw.get(
                        f"{prefix}_roll_number"
                    )

        # ==================================================================
        # 13. MARK SUBMISSION SYNCED
        # ==================================================================

        submission.student_id = student.user_id
        submission.status = SubmissionStatus.SYNCED
        submission.synced_at = datetime.now(
            submitted_at.tzinfo
        )
        submission.error_message = None

        # ==================================================================
        # 14. AUDIT LOG
        # ==================================================================

        if is_new_registration:

            log_action(
                db,
                user_id=None,
                action="STUDENT_ACCOUNT_CREATED",
                entity_type="student",
                entity_id=str(student.user_id),
                metadata={
                    "google_response_id": google_response_id,
                    "registration_submission_id": str(
                        submission.id
                    ),
                    "roll_number": roll_number,
                },
            )

        else:

            log_action(
                db,
                user_id=None,
                action="STUDENT_REGISTRATION_UPDATED",
                entity_type="student",
                entity_id=str(student.user_id),
                metadata={
                    "google_response_id": google_response_id,
                    "registration_submission_id": str(
                        submission.id
                    ),
                    "roll_number": roll_number,
                },
            )

        log_action(
            db,
            user_id=None,
            action="REGISTRATION_SYNCED",
            entity_type="registration_submission",
            entity_id=str(submission.id),
            metadata={
                "batch_id": str(form.batch_id),
                "student_id": str(student.user_id),
                "roll_number": roll_number,
            },
        )

        db.commit()

        # ==================================================================
        # 15. PROFILE PHOTO
        # ==================================================================

        if raw.get("profile_photo_file_id"):

            _attach_profile_photo(
                db,
                student,
                raw["profile_photo_file_id"],
            )

        # ==================================================================
        # 16. STUDENT ACTIVATION ONLY
        # ==================================================================

        # ONLY the student's User can enter this path.
        #
        # Father/mother/guardian are StudentContact records.
        # They never receive:
        #   - User
        #   - password
        #   - activation token
        #   - activation email

        if is_new_registration:

            _issue_student_activation(
                db=db,
                user=user,
                student=student,
                batch_name=form.batch.name,
            )

        return submission

    # ======================================================================
    # REQUIRED FIELD ERROR
    # ======================================================================

    except KeyError as exc:

        db.rollback()

        submission = (
            db.get(
                RegistrationSubmission,
                submission.id,
            )
            or submission
        )

        submission.status = SubmissionStatus.REJECTED

        submission.error_message = (
            f"Missing required field in submission: {exc}"
        )

        db.add(submission)

        log_action(
            db,
            user_id=None,
            action="REGISTRATION_REJECTED",
            entity_type="registration_submission",
            entity_id=str(submission.id),
            metadata={
                "reason": str(exc),
                "google_response_id": google_response_id,
            },
        )

        db.commit()

        return submission

    # ======================================================================
    # DATABASE CONFLICT
    # ======================================================================

    except IntegrityError as exc:

        logger.exception(
            "REGISTRATION SYNC INTEGRITY ERROR"
        )

        db.rollback()

        submission = (
            db.get(
                RegistrationSubmission,
                submission.id,
            )
            or submission
        )

        submission.status = SubmissionStatus.FAILED

        submission.error_message = str(exc.orig)

        db.add(submission)

        db.commit()

        return submission


# ============================================================================
# DATE PARSER
# ============================================================================


def _parse_iso_date(
    value: str | None,
) -> date | None:

    if not value:
        return None

    try:
        return date.fromisoformat(value)

    except ValueError:
        return None


# ============================================================================
# STUDENT ACTIVATION
# ============================================================================


def _issue_student_activation(
    db: Session,
    user: User,
    student: Student,
    batch_name: str | None = None,
) -> None:
    """
    Issue activation ONLY for the student's CoreSight account.

    Father/mother/guardian contacts never reach this function.
    """

    # Safety check.
    if user.role != Role.STUDENT:
        logger.error(
            "Refusing activation for non-student user=%s",
            user.id,
        )
        return

    # Never create activation token for an active account.
    if user.is_active:
        return

    raw_token = activation_service.create_activation_token(
        db,
        user,
    )

    db.commit()

    try:

        activation_service.send_student_activation_email(
            user=user,
            raw_token=raw_token,
            student_name=student.full_name,
            batch_name=batch_name,
        )

    except NotImplementedError:

        pass

    except Exception:

        # Registration has already succeeded.
        # Email failure must not undo registration.

        logger.exception(
            "Failed to send student activation email to %s",
            user.email,
        )


# ============================================================================
# PROFILE PHOTO
# ============================================================================


def _attach_profile_photo(
    db: Session,
    student: Student,
    drive_file_id: str,
) -> None:
    """
    Best-effort profile photo attachment.

    A profile-photo failure must never fail registration.
    """

    from app.services.storage_service import (
        ProfilePhotoError,
        upload_profile_photo_from_drive,
    )

    try:

        path = upload_profile_photo_from_drive(
            drive_file_id,
            student.user_id,
        )

        student.profile_photo_path = path

        db.commit()

    except ProfilePhotoError as exc:

        logger.warning(
            "PROFILE_PHOTO_SKIPPED student_id=%s reason=%s",
            student.user_id,
            exc,
        )


# ============================================================================
# CONTACT UPSERT
# ============================================================================


def _upsert_contact(
    db: Session,
    student_id: uuid.UUID,
    contact_type: ContactType,
    name: str,
    mobile: str | None,
    is_primary: bool = False,
) -> None:
    """
    Create/update a contact belonging to the student.

    IMPORTANT:
    This function NEVER creates a User.

    A FATHER/MOTHER/GUARDIAN contact is simply information associated
    with the student.
    """

    # No mobile submitted -> don't create a contact.
    if not mobile:
        return

    existing = (
        db.query(StudentContact)
        .filter(
            StudentContact.student_id == student_id,
            StudentContact.contact_type == contact_type,
        )
        .first()
    )

    if existing:

        existing.mobile_number = mobile

        if name:
            existing.name = name

        existing.is_primary = is_primary

        return

    db.add(
        StudentContact(
            student_id=student_id,
            contact_type=contact_type,
            name=name or contact_type.value.title(),
            mobile_number=mobile,
            is_primary=is_primary,
        )
    )