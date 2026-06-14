"""Envío de email por SMTP (compatible con Gmail mediante contraseña de aplicación).

Solo se conecta a la red si el SMTP está configurado (host + remitente). La
configuración se gestiona desde la pestaña Ajustes (se guarda en la BD).
"""
from __future__ import annotations

import logging
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from app import runtime_config
from app.security.sanitization import summarize_for_log

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class EmailConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str
    use_tls: bool


def config_from_runtime() -> EmailConfig:
    sender = str(runtime_config.effective("smtp_from") or "") or str(runtime_config.effective("smtp_user") or "")
    return EmailConfig(
        host=str(runtime_config.effective("smtp_host") or ""),
        port=int(runtime_config.effective("smtp_port") or 587),
        user=str(runtime_config.effective("smtp_user") or ""),
        password=str(runtime_config.effective("smtp_password") or ""),
        sender=sender,
        use_tls=bool(runtime_config.effective("smtp_use_tls")),
    )


def is_configured(cfg: EmailConfig | None = None) -> bool:
    cfg = cfg or config_from_runtime()
    return bool(cfg.host and cfg.sender)


def valid_email(address: str) -> bool:
    return bool(address and _EMAIL_RE.match(address.strip()))


def default_recipient() -> str:
    return str(runtime_config.effective("notify_email") or "")


def send_email(
    to: str, subject: str, html: str, text: str | None = None,
    *, cfg: EmailConfig | None = None, timeout: int = 20,
) -> tuple[bool, str]:
    """Envía un email HTML. Devuelve (ok, mensaje). Nunca lanza."""
    cfg = cfg or config_from_runtime()
    if not is_configured(cfg):
        return False, "SMTP no configurado: define el servidor y el remitente en Ajustes."
    if not valid_email(to):
        return False, f"Destinatario inválido: '{to}'."

    msg = EmailMessage()
    msg["From"] = cfg.sender
    msg["To"] = to.strip()
    msg["Subject"] = subject
    msg.set_content(text or "Este mensaje contiene un informe en formato HTML.")
    msg.add_alternative(html, subtype="html")

    try:
        context = ssl.create_default_context()
        if cfg.port == 465:
            with smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=timeout, context=context) as server:
                if cfg.user:
                    server.login(cfg.user, cfg.password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg.host, cfg.port, timeout=timeout) as server:
                if cfg.use_tls:
                    server.starttls(context=context)
                if cfg.user:
                    server.login(cfg.user, cfg.password)
                server.send_message(msg)
        logger.info("Email enviado", extra={"extra_data": {"to": to.strip(), "subject": subject[:80]}})
        return True, f"Email enviado a {to.strip()}."
    except Exception as exc:  # noqa: BLE001 - frontera de red controlada
        detail = summarize_for_log(str(exc), 200)
        logger.warning("Fallo enviando email: %s", detail)
        return False, f"Error enviando email: {detail}"
