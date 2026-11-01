from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


def send_email(recipient: str, subject: str, body: str) -> None:
    """Deliver a plain-text identity email using configured SMTP with TLS."""
    if not settings.smtp_host.strip() or not settings.smtp_sender.strip():
        raise RuntimeError("SMTP email delivery is not configured")
    message = EmailMessage()
    message["From"] = settings.smtp_sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    timeout = 10
    context = ssl.create_default_context()
    if settings.smtp_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=timeout, context=context) as client:
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
        return
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as client:
        client.ehlo()
        if settings.smtp_starttls:
            client.starttls(context=context)
            client.ehlo()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)
