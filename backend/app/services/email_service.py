import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import get_settings


def send_faculty_credentials_email(
    email: str,
    full_name: str,
    temporary_password: str,
):
    settings = get_settings()

    if not settings.smtp_host:
        raise RuntimeError(
            "SMTP is not configured"
        )

    subject = "Your CoreSight Faculty Account"

    body = f"""
Hello {full_name},

Your faculty registration request for CoreSight has been approved.

You can now sign in using the following credentials:

Email:
{email}

Temporary Password:
{temporary_password}

Login here:
{settings.frontend_url}/login

IMPORTANT:

You will be required to create a new password after your first login.

Please do not share these credentials with anyone.

Regards,
CoreSight Administration
"""

    message = MIMEMultipart()

    message["From"] = settings.smtp_from_email
    message["To"] = email
    message["Subject"] = subject

    message.attach(
        MIMEText(body, "plain")
    )

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