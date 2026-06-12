"""Herramienta defensiva de seguridad de prompts.

Detecta patrones habituales de inyección de prompts en una entrada de texto
para proteger sistemas LLM propios: NO genera payloads de ataque, solo
identifica indicios y propone mitigaciones.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.tools._text_utils import make_snippet
from app.tools.base import BaseTool, ToolContext

_PATTERNS: list[dict[str, Any]] = [
    {
        "id": "instruction_override",
        "category": "Anulación de instrucciones",
        "risk": "high",
        "regex": re.compile(
            r"(?i)(ignore (all |the )?(previous|above|prior) (instructions|rules)|"
            r"ignora (todas )?(las )?instrucciones (anteriores|previas)|"
            r"olvida (todo )?lo (anterior|que te han dicho)|disregard (the )?(system|previous))"
        ),
    },
    {
        "id": "role_manipulation",
        "category": "Manipulación de rol",
        "risk": "high",
        "regex": re.compile(
            r"(?i)(you are now|act as if you (have no|are not)|finge que (no tienes|eres)|"
            r"a partir de ahora eres|pretend (to be|you are)|jailbreak|developer mode|modo desarrollador|\bDAN\b)"
        ),
    },
    {
        "id": "system_prompt_leak",
        "category": "Exfiltración del system prompt",
        "risk": "high",
        "regex": re.compile(
            r"(?i)(reveal|show|print|repeat|muestra|imprime|repite)\s+(your|the|tu|el)\s+(system prompt|prompt de sistema|instructions|instrucciones internas)"
        ),
    },
    {
        "id": "secret_extraction",
        "category": "Extracción de secretos/credenciales",
        "risk": "high",
        "regex": re.compile(
            r"(?i)(dame|dime|give me|what is)\s+(la |el |the )?(api key|contrase[ñn]a|password|token|secret key|clave secreta)"
        ),
    },
    {
        "id": "exfiltration_channel",
        "category": "Canal de exfiltración (URLs/peticiones salientes)",
        "risk": "medium",
        "regex": re.compile(
            r"(?i)(env[ií]a(lo)?|send (it|this|the data)|post (it|this))\s+(a|to)\s+https?://"
        ),
    },
    {
        "id": "tool_abuse",
        "category": "Abuso de herramientas/sistema",
        "risk": "high",
        "regex": re.compile(
            r"(?i)(execute|run|ejecuta)\s+(this\s+)?(command|comando|shell|script)|rm\s+-rf|del\s+/s|format\s+c:"
        ),
    },
    {
        "id": "delimiter_injection",
        "category": "Inyección de delimitadores/roles falsos",
        "risk": "medium",
        "regex": re.compile(
            r"(?i)(<\s*/?system\s*>|\[/?INST\]|###\s*(system|instruction)|^\s*(system|assistant)\s*:)",
            re.MULTILINE,
        ),
    },
    {
        "id": "encoded_payload",
        "category": "Posible payload codificado (base64 largo)",
        "risk": "low",
        "regex": re.compile(r"[A-Za-z0-9+/]{120,}={0,2}"),
    },
    {
        "id": "policy_evasion",
        "category": "Evasión de políticas",
        "risk": "medium",
        "regex": re.compile(
            r"(?i)(sin (filtros|restricciones|censura)|without (filters|restrictions|refusing)|"
            r"no (te )?niegues|never refuse|bypass (the )?(safety|policy|filters?))"
        ),
    },
]

_MITIGATIONS = [
    "Separar siempre instrucciones de sistema y datos de usuario (no concatenar sin delimitar).",
    "Tratar el contenido de documentos y usuarios como datos no confiables (no como instrucciones).",
    "Limitar las herramientas disponibles por agente (allow-list) y validar sus entradas.",
    "No incluir secretos en prompts; usar configuración local y redacción en logs.",
    "Registrar y revisar entradas con patrones de inyección (este análisis) antes de procesarlas.",
    "Aplicar validación de salida (verificador) antes de mostrar o ejecutar resultados.",
]

_RISK_WEIGHT = {"high": 3, "medium": 2, "low": 1}


class CheckPromptInjectionPatternsInput(BaseModel):
    text: str = Field(min_length=1, max_length=100000, description="Texto/prompt a analizar")


class CheckPromptInjectionPatternsTool(BaseTool):
    name = "check_prompt_injection_patterns"
    category = "prompt_security"
    description = (
        "Análisis defensivo: detecta patrones de inyección de prompts (anulación "
        "de instrucciones, manipulación de rol, exfiltración...) y sugiere mitigaciones."
    )
    input_schema = CheckPromptInjectionPatternsInput
    timeout_seconds = 10

    def execute(self, payload: CheckPromptInjectionPatternsInput, ctx: ToolContext) -> dict[str, Any]:
        findings: list[dict[str, str]] = []
        for spec in _PATTERNS:
            match = spec["regex"].search(payload.text)
            if match:
                findings.append(
                    {
                        "pattern_id": spec["id"],
                        "category": spec["category"],
                        "risk": spec["risk"],
                        "snippet": make_snippet(payload.text, match.group(0), 200),
                    }
                )

        score = sum(_RISK_WEIGHT[f["risk"]] for f in findings)
        if score >= 5:
            overall = "high"
        elif score >= 3:
            overall = "medium"
        elif score >= 1:
            overall = "low"
        else:
            overall = "none"

        return {
            "findings": findings,
            "finding_count": len(findings),
            "overall_risk": overall,
            "risk_score": score,
            "mitigations": _MITIGATIONS if findings else [],
            "note": (
                "Detección por patrones: una entrada limpia no garantiza ausencia de "
                "inyección y un hallazgo no implica intención maliciosa. Uso defensivo."
            ),
        }
