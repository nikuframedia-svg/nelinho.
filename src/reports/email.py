"""ProdPlan ONE — Report email delivery (Sprint Q.22.F).

SMTP delivery for generated reports. Uses the stdlib ``smtplib`` /
``email`` packages — no extra dependency. The blocking SMTP call runs
in a worker thread (``asyncio.to_thread``) so the event loop is free.

When ``settings.smtp_enabled`` is ``False`` (the dev default) nothing
connects to a server: the delivery is logged and reported as
``skipped`` so callers still record a deterministic outcome.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from src.shared.config import settings

logger = logging.getLogger("reports.email")


class EmailDeliveryError(RuntimeError):
    """Erro de entrega SMTP (lançado só quando ``smtp_enabled`` é True)."""


def _send_blocking(message: EmailMessage) -> None:
    """Envio SMTP síncrono — corre via ``asyncio.to_thread``."""
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
    """Envia um relatório por email para ``recipients``.

    Devolve ``{"sent": bool, "skipped": bool, "recipients": [...]}``.
    ``skipped`` é True quando o SMTP está desligado ou não há
    destinatários — nenhum dos dois é erro.
    """
    if not recipients:
        logger.info("send_report_email: sem destinatários — nada a fazer")
        return {"sent": False, "skipped": True, "recipients": []}

    if not settings.smtp_enabled:
        logger.info(
            "send_report_email: SMTP desligado — enviaria %r para %s",
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
    except Exception as exc:  # smtplib lança uma família de OSError/SMTPException
        logger.warning("send_report_email falhou: %s", exc)
        raise EmailDeliveryError(
            f"Falha ao enviar relatório por email: {exc}"
        ) from exc

    logger.info("send_report_email: enviado %r para %s", subject, recipients)
    return {"sent": True, "skipped": False, "recipients": list(recipients)}
