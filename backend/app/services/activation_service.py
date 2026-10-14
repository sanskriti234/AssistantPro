"""
Account activation service.

Users created through CoreSight registration/sync initially have an
inactive account and no usable password.

This service:
- generates a secure, single-use activation token
- stores only the SHA-256 hash of the token
- expires tokens after 48 hours
- sends the raw token through an activation email
- activates the account when the user creates a password
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import smtplib
from datetime import timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.database.base import utcnow
from app.database.models import (
    AccountActivationToken,
    User,
)
from app.services.audit import log_action





logger = logging.getLogger("coresight.activation")


# Activation links remain valid for 48 hours.
TOKEN_TTL = timedelta(hours=48)


# ============================================================
# Token hashing
# ============================================================

def _hash_token(raw_token: str) -> str:
    """
    Hash an activation token before storing it in the database.

    The raw token is never persisted.
    """

    return hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()


# ============================================================
# Create activation token
# ============================================================

def create_activation_token(
    db: Session,
    user: User,
) -> str:
    """
    Create a new single-use activation token.

    Any previous unused token belonging to the user is invalidated.

    Returns:
        Raw activation token.

    Important:
        The raw token must only be passed to the email-delivery
        function. It must never be stored or logged.
    """

    # --------------------------------------------------------
    # Invalidate previous unused tokens
    # --------------------------------------------------------

    db.query(AccountActivationToken).filter(
        AccountActivationToken.user_id == user.id,
        AccountActivationToken.used_at.is_(None),
    ).delete()

    # --------------------------------------------------------
    # Generate secure random token
    # --------------------------------------------------------

    raw_token = secrets.token_urlsafe(32)

    # --------------------------------------------------------
    # Store only the hash
    # --------------------------------------------------------

    token = AccountActivationToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=utcnow() + TOKEN_TTL,
    )

    db.add(token)

    # Make sure the token exists in the current transaction.
    db.flush()

    return raw_token


# ============================================================
# Send activation email
# ============================================================

def send_activation_email(
    user: User,
    raw_token: str,
) -> None:
    """
    Send an account activation email.

    The raw activation token is placed only in the activation URL.
    It is never stored in the database or logged.
    """

    settings = get_settings()

    # --------------------------------------------------------
    # Validate SMTP configuration
    # --------------------------------------------------------

    required_settings = {
        "SMTP_HOST": settings.smtp_host,
        "SMTP_USERNAME": settings.smtp_username,
        "SMTP_PASSWORD": settings.smtp_password,
        "SMTP_FROM_EMAIL": settings.smtp_from_email,
    }

    missing = [
        name
        for name, value in required_settings.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Email delivery is not configured. "
            f"Missing settings: {', '.join(missing)}"
        )

    # --------------------------------------------------------
    # Build activation URL
    # --------------------------------------------------------

    activation_url = (
        f"{settings.frontend_url}/activate"
        f"?token={quote(raw_token)}"
    )

    # --------------------------------------------------------
    # Build email
    # --------------------------------------------------------

    message = EmailMessage()

    message["Subject"] = "Your CoreSight Faculty Account"
    message["From"] = settings.smtp_from_email
    message["To"] = user.email

    message.set_content(
        f"""Hello,

Your CoreSight faculty account has been approved.

Login email:
{user.email}

To activate your account and create your password, open the link below:

{activation_url}

This activation link is single-use and expires after 48 hours.

After activation, you can log in to CoreSight using your institutional
email address and the password you create.

If you did not request a CoreSight faculty account, please ignore this email.

Regards,
CoreSight
"""
    )

    # --------------------------------------------------------
    # Send through SMTP
    # --------------------------------------------------------

    with smtplib.SMTP(
        settings.smtp_host,
        settings.smtp_port,
        timeout=30,
    ) as server:

        server.starttls()

        server.login(
            settings.smtp_username,
            settings.smtp_password,
        )

        server.send_message(message)

    logger.info(
        "Faculty activation email sent to %s",
        user.email,
    )


# ============================================================
# Activate account
# ============================================================

def send_student_activation_email(
    user: User,
    raw_token: str,
    student_name: str | None = None,
    batch_name: str | None = None,
) -> None:
    settings = get_settings()

    # Validate SMTP configuration.
    required_settings = {
        "SMTP_HOST": settings.smtp_host,
        "SMTP_USERNAME": settings.smtp_username,
        "SMTP_PASSWORD": settings.smtp_password,
        "SMTP_FROM_EMAIL": settings.smtp_from_email,
    }

    missing = [
        name
        for name, value in required_settings.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Email delivery is not configured. "
            f"Missing settings: {', '.join(missing)}"
        )

    if not user.email:
        raise ValueError("Student email address is missing.")

    # Build activation URL.
    activation_url = (
        f"{settings.frontend_url.rstrip('/')}/activate"
        f"?token={quote(raw_token, safe='')}"
    )

    greeting = (
        f"Hello {student_name},"
        if student_name
        else "Hello,"
    )

    batch_text = (
        f"Your registration for {batch_name} has been successfully completed."
        if batch_name
        else "Your student registration has been successfully completed."
    )

    message = EmailMessage()
    message["Subject"] = "Activate Your CoreSight Student Account"
    message["From"] = settings.smtp_from_email
    message["To"] = user.email

    message.set_content(
        f"""{greeting}

{batch_text}

Your CoreSight student account has been created.

Registered email:
{user.email}

Activate your account and create your password using this link:

{activation_url}

This activation link is single-use and expires after 48 hours.

If you did not register for a CoreSight student account, please ignore
this email.

Regards,
CoreSight
"""
    )

    with smtplib.SMTP(
        settings.smtp_host,
        settings.smtp_port,
        timeout=30,
    ) as server:
        if settings.smtp_use_tls:
            server.starttls()

        server.login(
            settings.smtp_username,
            settings.smtp_password,
        )

        server.send_message(message)

    logger.info(
        "Student activation email sent to %s",
        user.email,
    )


def activate_account(
    db: Session,
    raw_token: str,
    new_password: str,
) -> User:
    """
    Redeem an activation token and activate the account.

    The token must:
    - exist
    - not already be used
    - not be expired

    The user's password is replaced with the newly created password.
    """

    # --------------------------------------------------------
    # Validate password
    # --------------------------------------------------------

    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    # --------------------------------------------------------
    # Hash supplied token
    # --------------------------------------------------------

    token_hash = _hash_token(raw_token)

    # --------------------------------------------------------
    # Find token
    # --------------------------------------------------------

    token = (
        db.query(AccountActivationToken)
        .filter(
            AccountActivationToken.token_hash == token_hash
        )
        .first()
    )

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token",
        )

    # --------------------------------------------------------
    # Check whether token was already used
    # --------------------------------------------------------

    if token.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This activation token has already been used",
        )

    # --------------------------------------------------------
    # Check expiry
    # --------------------------------------------------------

    # Normalize the stored expiry timestamp to UTC.
    expires_at = token.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    else:
        expires_at = expires_at.astimezone(timezone.utc)

    if expires_at < utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This activation token has expired",
        )

    # --------------------------------------------------------
    # Find user
    # --------------------------------------------------------

    user = db.get(
        User,
        token.user_id,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token",
        )

    # --------------------------------------------------------
    # Set password
    # --------------------------------------------------------

    user.password_hash = hash_password(
        new_password
    )

    # --------------------------------------------------------
    # Activate account
    # --------------------------------------------------------

    user.is_active = True

    # --------------------------------------------------------
    # Mark token as used
    # --------------------------------------------------------

    token.used_at = utcnow()

    db.commit()

    # --------------------------------------------------------
    # Audit log
    # --------------------------------------------------------

    log_action(
        db,
        user_id=user.id,
        action="ACCOUNT_ACTIVATED",
        entity_type="user",
        entity_id=str(user.id),
    )

    db.commit()

    db.refresh(user)

    return user

def send_faculty_approval_email(
    user: User,
    temporary_password: str,
) -> None:

    settings = get_settings()

    login_url = f"{settings.frontend_url}/login"

    message = EmailMessage()

    message["Subject"] = "Your CoreSight Faculty Account Has Been Approved"
    message["From"] = settings.smtp_from_email
    message["To"] = user.email

    message.set_content(
        f"""Hello,

Your faculty registration request for CoreSight has been approved.

You can now access the CoreSight portal.

LOGIN DETAILS

Email:
{user.email}

Temporary Password:
{temporary_password}

Login here:
{login_url}

IMPORTANT:
You will be required to create a new password after logging in.

Do not share your temporary password with anyone.

Regards,
CoreSight Administration
"""
    )

    with smtplib.SMTP(
        settings.smtp_host,
        settings.smtp_port,
    ) as server:

        server.starttls()

        server.login(
            settings.smtp_username,
            settings.smtp_password,
        )

        server.send_message(message)