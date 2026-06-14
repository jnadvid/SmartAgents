"""Tests del envío de email (SMTP mockeado)."""
from __future__ import annotations

from app import runtime_config
from app.notifications import email


def test_not_configured_returns_error() -> None:
    ok, message = email.send_email("dest@test.com", "Asunto", "<p>x</p>")
    assert ok is False and "configurado" in message.lower()


def test_invalid_recipient() -> None:
    runtime_config.set_overlay({"smtp_host": "smtp.test", "smtp_from": "me@test.com"})
    ok, message = email.send_email("no-es-un-email", "Asunto", "<p>x</p>")
    assert ok is False and "inválido" in message.lower()


def test_sends_with_starttls_and_login(monkeypatch) -> None:
    runtime_config.set_overlay({
        "smtp_host": "smtp.test", "smtp_from": "me@test.com", "smtp_port": 587,
        "smtp_use_tls": True, "smtp_user": "u", "smtp_password": "p",
    })
    captured: dict = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=20):
            captured["host"], captured["port"] = host, port

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self, context=None):
            captured["tls"] = True

        def login(self, user, password):
            captured["login"] = (user, password)

        def send_message(self, msg):
            captured["to"] = msg["To"]
            captured["subject"] = msg["Subject"]

    monkeypatch.setattr(email.smtplib, "SMTP", FakeSMTP)
    ok, message = email.send_email("dest@test.com", "Informe", "<p>hola</p>")
    assert ok is True
    assert captured["to"] == "dest@test.com"
    assert captured["tls"] is True
    assert captured["login"] == ("u", "p")
