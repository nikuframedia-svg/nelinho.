"""
ProdPlan ONE - Report Email Delivery
=====================================

SMTP delivery for generated reports. Uses the stdlib ``smtplib`` /
``email`` packages — no extra dependency. The blocking SMTP call runs
in a worker thread (``asyncio.to_thread``) so the event loop is free.

When ``settings.smtp_enabled`` is ``False`` (the dev default) nothing
connects to a server: the delivery is logged and reported as
``skipped`` so callers still record a deterministic outcome.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from src.shared.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when an SMTP send fails while ``smtp_enabled`` is True."""


def _send_blocking(message: EmailMessage) -> None:
    """Synchronous SMTP send — run via ``asyncio.to_thread``."""
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


async def send_report_email(
    recipients: list[str],
    subject: str,
    body: str,
    *,
    attachment_name: Optional[str] = None,
    attachment_text: Optional[str] = None,
) -> dict:
    """Send a report email to ``recipients``.

    Returns ``{"sent": bool, "skipped": bool, "recipients": [...]}``.
    ``skipped`` is True when SMTP is disabled or there are no recipients
    — neither is an error.
    """
    if not recipients:
        logger.info("send_report_email: no recipients — nothing to do")
        return {"sent": False, "skipped": True, "recipients": []}

    if not settings.smtp_enabled:
        logger.info(
            "send_report_email: SMTP disabled — would send %r to %s",
            subject, recipients,
        )
        return {"sent": False, "skipped": True, "recipients": list(recipients)}

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)
    if attachment_name and attachment_text is not None:
        message.add_attachment(
            attachment_text.encode("utf-8"),
            maintype="text",
            subtype="plain",
            filename=attachment_name,
        )

    try:
        await asyncio.to_thread(_send_blocking, message)
    except Exception as exc:  # smtplib raises a family of OSError/SMTPException
        logger.warning("send_report_email failed: %s", exc)
        raise EmailDeliveryError(str(exc)) from exc

    logger.info("send_report_email: sent %r to %s", subject, recipients)
    return {"sent": True, "skipped": False, "recipients": list(recipients)}
