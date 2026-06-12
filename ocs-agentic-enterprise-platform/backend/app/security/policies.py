"""Políticas de seguridad de agentes y herramientas.

Reglas del MVP:
- Un agente solo puede invocar herramientas presentes en su `allowed_tools`.
- Las herramientas no ejecutan comandos del sistema ni acceden a Internet.
- Las herramientas solo tocan datos dentro de `backend/data`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings


class PolicyViolation(Exception):
    """Violación de una política de seguridad de la plataforma."""


@dataclass(frozen=True)
class SecurityPolicy:
    """Política aplicable a un agente."""

    name: str
    description: str
    max_tool_calls: int = 5
    max_output_chars: int = 40000
    allow_document_access: bool = True
    risk_level: str = "standard"
    notes: list[str] = field(default_factory=list)


POLICIES: dict[str, SecurityPolicy] = {
    "standard": SecurityPolicy(
        name="standard",
        description="Política por defecto para agentes empresariales.",
        max_tool_calls=5,
        risk_level="standard",
    ),
    "sensitive": SecurityPolicy(
        name="sensitive",
        description=(
            "Política para dominios sensibles (legal, finanzas, ciberseguridad): "
            "misma capacidad técnica, salidas marcadas con descargos de responsabilidad."
        ),
        max_tool_calls=6,
        risk_level="sensitive",
        notes=["La salida debe incluir descargo de responsabilidad profesional."],
    ),
    "security_testing": SecurityPolicy(
        name="security_testing",
        description=(
            "Política para pruebas de seguridad defensivas sobre sistemas propios "
            "y autorizados. No genera payloads ofensivos operativos."
        ),
        max_tool_calls=4,
        risk_level="elevated",
        notes=["Solo análisis defensivo y recomendaciones de hardening."],
    ),
}


def get_policy(name: str) -> SecurityPolicy:
    return POLICIES.get(name, POLICIES["standard"])


def ensure_tool_allowed(agent_name: str, allowed_tools: list[str], tool_name: str) -> None:
    """Lanza PolicyViolation si el agente no tiene autorizada la herramienta."""
    if tool_name not in allowed_tools:
        raise PolicyViolation(
            f"El agente '{agent_name}' no tiene autorizada la herramienta '{tool_name}'."
        )


def ensure_path_in_data_dir(path: Path) -> Path:
    """Garantiza que una ruta queda dentro de backend/data (anti path traversal)."""
    settings = get_settings()
    data_dir = settings.data_dir.resolve()
    resolved = path.resolve()
    if data_dir != resolved and data_dir not in resolved.parents:
        raise PolicyViolation(
            f"Acceso denegado: la ruta '{resolved}' está fuera del directorio de datos."
        )
    return resolved


def ensure_input_size(text: str) -> None:
    """Valida el tamaño máximo de entrada definido en configuración."""
    settings = get_settings()
    if len(text or "") > settings.max_input_chars:
        raise PolicyViolation(
            f"La entrada supera el máximo permitido de {settings.max_input_chars} caracteres."
        )
