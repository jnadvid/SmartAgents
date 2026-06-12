"""Sanitización de textos para logs, auditoría y salidas.

Objetivo: que el Chain-of-Work y los logs nunca contengan secretos,
tokens ni texto sin truncar.
"""
from __future__ import annotations

import re
import unicodedata

REDACTED = "[REDACTADO]"

# Patrones de secretos habituales. Conservadores a propósito: es preferible
# redactar de más en un registro de auditoría que filtrar un secreto.
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[a-z0-9._\-]{12,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    (
        "assignment_secret",
        re.compile(
            r"(?i)\b(api[_-]?key|apikey|secret|token|password|passwd|contrase[ñn]a|clave)\b\s*[:=]\s*['\"]?[^\s'\"]{6,}"
        ),
    ),
]

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(text: str) -> str:
    """Elimina caracteres de control y normaliza saltos de línea."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL_CHARS.sub("", text)


def redact_secrets(text: str) -> str:
    """Sustituye posibles secretos por un marcador de redacción."""
    if not text:
        return ""
    redacted = text
    for _name, pattern in SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def find_secret_patterns(text: str) -> list[str]:
    """Devuelve los nombres de patrones de secreto detectados en el texto."""
    if not text:
        return []
    return [name for name, pattern in SECRET_PATTERNS if pattern.search(text)]


def truncate(text: str, max_chars: int = 400) -> str:
    """Trunca un texto añadiendo un sufijo informativo."""
    if text is None:
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "… [truncado]"


def summarize_for_log(text: str, max_chars: int = 400) -> str:
    """Versión segura de un texto para logs/auditoría: limpia, redacta y trunca."""
    return truncate(redact_secrets(clean_text(text or "")), max_chars)


def normalize_for_matching(text: str) -> str:
    """Minúsculas y sin acentos: facilita la comparación de palabras clave."""
    if not text:
        return ""
    lowered = text.lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))
