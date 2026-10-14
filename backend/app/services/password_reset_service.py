from __future__ import annotations

import hashlib
import secrets
import smtplib

from datetime import timedelta
from email.message import EmailMessage
from urllib.parse import quote

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.database.base import utcnow
from app.database.models import PasswordResetToken, User


RESET_TOKEN_TTL = timedelta(hours=1)


# ============================================================
# Token hashing
# ============================================================

def hash_token(raw_token: str) -> str:
    return hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()


# ============================================================
# Create password reset token
# ============================================================

def create_password_reset_token(
    db: Session,
    user: User,
) -> str:

    # Invalidate all previous unused tokens
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).delete()

    # Generate secure random token
    raw_token = secrets.token_urlsafe(32)

    # Store only hashed token
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=utcnow() + RESET_TOKEN_TTL,
    )

    db.add(token)
    db.flush()

    return raw_token


# ============================================================
# Send password reset email
# ============================================================

def send_password_reset_email(
    user: User,
    raw_token: str,
) -> None:

    settings = get_settings()

    required_settings = {
        "SMTP_HOST": settings.smtp_host,
        "SMTP_PORT": settings.smtp_port,
        "SMTP_USERNAME": settings.smtp_username,
        "SMTP_PASSWORD": settings.smtp_password,
        "SMTP_FROM_EMAIL": settings.smtp_from_email,
        "FRONTEND_URL": settings.frontend_url,
    }

    missing = [
        name
        for name, value in required_settings.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Password reset email is not configured. "
            f"Missing settings: {', '.join(missing)}"
        )

    reset_url = (
        f"{settings.frontend_url.rstrip('/')}"
        f"/reset-password/{quote(raw_token, safe='')}"
    )

    message = EmailMessage()

    message["Subject"] = "Reset your CoreSight password"
    message["From"] = settings.smtp_from_email
    message["To"] = user.email

    message.set_content(
        f"""Hello,

A password reset was requested for your CoreSight account.

To create a new password, open the link below:

{reset_url}

This password reset link:

- expires in 1 hour
- can only be used once
- becomes invalid when a new reset link is requested

If you did not request this password reset, you can safely ignore this email.

Regards,
CoreSight
"""
    )

    try:
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

    except Exception as exc:
        raise RuntimeError(
            f"Failed to send password reset email: {exc}"
        ) from exc


# ============================================================
# Reset password
# ============================================================

def reset_password(
    db: Session,
    raw_token: str,
    new_password: str,
) -> User:

    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    token_hash = hash_token(raw_token)

    token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash
        )
        .first()
    )

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset link",
        )

    if token.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link has already been used",
        )

    if token.expires_at < utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link has expired",
        )

    user = db.get(
        User,
        token.user_id,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset link",
        )

    # Set new password
    user.password_hash = hash_password(
        new_password
    )

    # Faculty/admin/etc. can use the account normally now
    user.must_change_password = False

    # Mark token as permanently used
    token.used_at = utcnow()

    db.commit()
    db.refresh(user)

    return user