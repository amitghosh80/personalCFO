import logging

import httpx

from ..config import get_settings

logger = logging.getLogger("personalcfo.email")

RESEND_API_URL = "https://api.resend.com/emails"


def send_email(to: str, subject: str, html: str) -> None:
    """Sends an email via Resend. No-ops with a warning if RESEND_API_KEY is unset,
    so local dev without Resend configured doesn't crash callers."""
    settings = get_settings()
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set; skipping email send")
        return

    response = httpx.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={"from": settings.email_from, "to": [to], "subject": subject, "html": html},
        timeout=10,
    )
    response.raise_for_status()


def send_password_reset_email(to: str, reset_link: str) -> None:
    subject = "Reset your PersonalCFO password"
    html = f"""
    <p>We received a request to reset your PersonalCFO password.</p>
    <p><a href="{reset_link}">Click here to choose a new password</a>. This link
    expires in 30 minutes.</p>
    <p>If you didn't request this, you can safely ignore this email.</p>
    """
    send_email(to, subject, html)
