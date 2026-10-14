from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid

from app.core.deps import get_current_user
from app.core.security import hash_password
from app.database.base import utcnow
from app.database.connection import get_db
from app.database.models import (
    Department,
    Faculty,
    FacultyRegistrationRequest,
    FacultyRegistrationStatus,
    Role,
    User,
)
from app.schemas.schemas import (
    FacultyRegistrationRejectRequest,
    FacultyRegistrationRequestCreate,
    FacultyRegistrationRequestResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    LoginRequest,
    LoginResponse,
    UserOut,
)

from app.services import activation_service
from app.services.auth_service import authenticate, resolve_user_out
import secrets
from app.services.password_reset_service import (
    create_password_reset_token,
    send_password_reset_email,
    reset_password,
)
from app.services.email_service import (
    send_faculty_credentials_email,
)
from app.services.credential_service import (
    generate_temporary_password,
)
router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================
# Activation
# ============================================================

class ActivateAccountRequest(BaseModel):
    token: str
    newPassword: str
class ChangePasswordRequest(BaseModel):
    new_password: str

@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be at least "
                "8 characters"
            ),
        )

    current_user.password_hash = hash_password(
        payload.new_password
    )

    current_user.must_change_password = False

    db.commit()

    return {
        "message": "Password updated successfully",
        "mustChangePassword": False,
    }

@router.post("/activate", response_model=UserOut)
def activate(
    body: ActivateAccountRequest,
    db: Session = Depends(get_db),
):
    """
    Public endpoint.

    The user receives a single-use activation token by email,
    then uses this endpoint to create their own password.
    """

    user = activation_service.activate_account(
        db,
        body.token,
        body.newPassword,
    )

    return resolve_user_out(user)


# ============================================================
# Login
# ============================================================

@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    result = authenticate(
        db,
        body.email,
        body.password,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user, token = result

    return LoginResponse(
    user=resolve_user_out(user),
    accessToken=token,
    mustChangePassword=user.must_change_password,
    )

@router.post("/forgot-password")
def forgot_password(
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    email = body.email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    # Prevent account enumeration
    if user is None:
        return {
            "message": (
                "If an account exists with this email, "
                "a password reset link has been sent."
            )
        }

    # --------------------------------------------------------
    # Create reset token
    # --------------------------------------------------------

    raw_token = create_password_reset_token(
        db,
        user,
    )

    # Persist token BEFORE email delivery
    db.commit()

    # --------------------------------------------------------
    # Send email
    # --------------------------------------------------------

    try:
        send_password_reset_email(
            user,
            raw_token,
        )

    except Exception as exc:

        print(
            "PASSWORD_RESET_EMAIL_FAILED "
            f"user={user.id} "
            f"error={exc}"
        )

        # Do not expose SMTP details publicly
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Unable to send password reset email. "
                "Please try again later."
            ),
        )

    return {
        "message": (
            "If an account exists with this email, "
            "a password reset link has been sent."
        )
    }

    
@router.post("/reset-password")
def reset_user_password(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
):

    reset_password(
        db=db,
        raw_token=body.token,
        new_password=body.new_password,
    )

    return {
        "message": "Password reset successfully"
    }
# ============================================================
# Current user
# ============================================================

@router.get("/me", response_model=UserOut)
def me(
    user: User = Depends(get_current_user),
):
    return resolve_user_out(user)


# ============================================================
# Faculty registration - public
# ============================================================

@router.post(
    "/faculty/register",
    response_model=FacultyRegistrationRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_faculty(
    payload: FacultyRegistrationRequestCreate,
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()
    employee_id = payload.employee_id.strip()

    # --------------------------------------------------------
    # Validate department
    # --------------------------------------------------------

    department = db.get(
        Department,
        payload.department_id,
    )

    if department is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    # --------------------------------------------------------
    # Check existing user
    # --------------------------------------------------------

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # --------------------------------------------------------
    # Check existing faculty
    # --------------------------------------------------------

    existing_faculty = (
        db.query(Faculty)
        .filter(Faculty.employee_id == employee_id)
        .first()
    )

    if existing_faculty:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Faculty ID is already registered",
        )

    # --------------------------------------------------------
    # Check pending request by Faculty ID
    # --------------------------------------------------------

    existing_request = (
        db.query(FacultyRegistrationRequest)
        .filter(
            FacultyRegistrationRequest.employee_id == employee_id,
            FacultyRegistrationRequest.status
            == FacultyRegistrationStatus.PENDING,
        )
        .first()
    )

    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A registration request for this Faculty ID "
                "is already pending"
            ),
        )

    # --------------------------------------------------------
    # Check pending request by email
    # --------------------------------------------------------

    existing_email_request = (
        db.query(FacultyRegistrationRequest)
        .filter(
            FacultyRegistrationRequest.email == email,
            FacultyRegistrationRequest.status
            == FacultyRegistrationStatus.PENDING,
        )
        .first()
    )

    if existing_email_request:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A registration request for this email "
                "is already pending"
            ),
        )

    # --------------------------------------------------------
    # Create registration request
    # --------------------------------------------------------

    registration = FacultyRegistrationRequest(
        full_name=payload.full_name.strip(),
        employee_id=employee_id,
        email=email,
        department_id=payload.department_id,
        designation=(
            payload.designation.strip()
            if payload.designation
            else None
        ),
        phone=(
            payload.phone.strip()
            if payload.phone
            else None
        ),
        status=FacultyRegistrationStatus.PENDING,
    )

    db.add(registration)
    db.commit()
    db.refresh(registration)

    return registration


# ============================================================
# Admin - list faculty registration requests
# ============================================================

@router.get("/admin/faculty/requests")
def list_faculty_registration_requests(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    requests = (
        db.query(FacultyRegistrationRequest)
        .order_by(
            FacultyRegistrationRequest.requested_at.desc()
        )
        .all()
    )

    return [
        {
            "id": str(request.id),
            "full_name": request.full_name,
            "employee_id": request.employee_id,
            "email": request.email,
            "department_id": str(request.department_id),
            "department_code": request.department.code,
            "department_name": request.department.name,
            "designation": request.designation,
            "phone": request.phone,
            "status": request.status.value,
            "requested_at": request.requested_at,
        }
        for request in requests
    ]


# ============================================================
# Admin - faculty registration details
# ============================================================

@router.get("/admin/faculty/requests/{request_id}")
def get_faculty_registration_request(
    request_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    registration = db.get(
        FacultyRegistrationRequest,
        request_id,
    )

    if registration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty registration request not found",
        )

    return {
        "id": str(registration.id),
        "full_name": registration.full_name,
        "employee_id": registration.employee_id,
        "email": registration.email,
        "department_id": str(registration.department_id),
        "department_code": registration.department.code,
        "department_name": registration.department.name,
        "designation": registration.designation,
        "phone": registration.phone,
        "status": registration.status.value,
        "requested_at": registration.requested_at,
        "reviewed_at": registration.reviewed_at,
        "reviewed_by": (
            str(registration.reviewed_by)
            if registration.reviewed_by
            else None
        ),
        "rejection_reason": registration.rejection_reason,
    }


# ============================================================
# Admin - approve faculty registration
# ============================================================

@router.post(
    "/admin/faculty/requests/{request_id}/approve"
)
def approve_faculty_registration(
    request_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # --------------------------------------------------------
    # Admin authorization
    # --------------------------------------------------------

    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    # --------------------------------------------------------
    # Find registration request
    # --------------------------------------------------------

    registration = db.get(
        FacultyRegistrationRequest,
        request_id,
    )

    if registration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty registration request not found",
        )

    # --------------------------------------------------------
    # Only pending requests can be approved
    # --------------------------------------------------------

    if registration.status != FacultyRegistrationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This registration request "
                "has already been reviewed"
            ),
        )

    # --------------------------------------------------------
    # Re-check email
    # --------------------------------------------------------

    existing_user = (
        db.query(User)
        .filter(User.email == registration.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # --------------------------------------------------------
    # Re-check employee ID
    # --------------------------------------------------------

    existing_faculty = (
        db.query(Faculty)
        .filter(
            Faculty.employee_id
            == registration.employee_id
        )
        .first()
    )

    if existing_faculty:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Faculty ID is already registered",
        )

    # --------------------------------------------------------
    # Generate temporary password
    # --------------------------------------------------------

    temporary_password = generate_temporary_password()

    # --------------------------------------------------------
    # Create faculty user
    # --------------------------------------------------------

    new_user = User(
        email=registration.email,
        password_hash=hash_password(
            temporary_password
        ),
        role=Role.FACULTY,
        is_active=True,

        # Force password change after login
        must_change_password=True,
    )

    db.add(new_user)

    # Generate ID before creating Faculty
    db.flush()

    # --------------------------------------------------------
    # Create faculty profile
    # --------------------------------------------------------

    new_faculty = Faculty(
        user_id=new_user.id,
        employee_id=registration.employee_id,
        name=registration.full_name,
        department_id=registration.department_id,
        phone=registration.phone,
    )

    db.add(new_faculty)

    # --------------------------------------------------------
    # Approve registration
    # --------------------------------------------------------

    registration.status = (
        FacultyRegistrationStatus.APPROVED
    )

    registration.reviewed_at = utcnow()

    registration.reviewed_by = user.id

    # --------------------------------------------------------
    # Commit database FIRST
    # --------------------------------------------------------

    db.commit()

    db.refresh(new_user)

    # --------------------------------------------------------
    # Send temporary credentials email
    # --------------------------------------------------------

    email_sent = True

    try:

        send_faculty_credentials_email(
            email=new_user.email,
            full_name=registration.full_name,
            temporary_password=temporary_password,
        )

    except Exception as exc:

        email_sent = False

        print(
            "FACULTY_CREDENTIAL_EMAIL_FAILED "
            f"user={new_user.id} "
            f"error={exc}"
        )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    if email_sent:

        message = (
            "Faculty registration approved. "
            "Temporary credentials have been sent by email."
        )

    else:

        message = (
            "Faculty registration approved, "
            "but the credentials email could not be sent."
        )

    return {
        "message": message,
        "user_id": str(new_user.id),
        "email": new_user.email,
        "email_sent": email_sent,
    }


# ============================================================
# Admin - reject faculty registration
# ============================================================

@router.post(
    "/admin/faculty/requests/{request_id}/reject"
)
def reject_faculty_registration(
    request_id: uuid.UUID,
    payload: FacultyRegistrationRejectRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    # --------------------------------------------------------
    # Find registration request
    # --------------------------------------------------------

    registration = db.get(
        FacultyRegistrationRequest,
        request_id,
    )

    if registration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty registration request not found",
        )

    # --------------------------------------------------------
    # Only pending requests can be rejected
    # --------------------------------------------------------

    if registration.status != FacultyRegistrationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This registration request has already been reviewed",
        )

    # --------------------------------------------------------
    # Save rejection
    # --------------------------------------------------------

    registration.status = FacultyRegistrationStatus.REJECTED
    registration.reviewed_at = utcnow()
    registration.reviewed_by = user.id
    registration.rejection_reason = payload.reason.strip()

    db.commit()

    return {
        "message": "Faculty registration rejected",
        "request_id": str(registration.id),
        "status": registration.status.value,
    }