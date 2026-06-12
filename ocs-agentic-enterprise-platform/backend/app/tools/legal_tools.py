"""Herramientas legales: revisión heurística de textos contractuales.

Detecta cláusulas, obligaciones y patrones de riesgo habituales.
No sustituye asesoría legal profesional.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.security.sanitization import normalize_for_matching
from app.tools._text_utils import split_sentences
from app.tools.base import BaseTool, ToolContext

_CLAUSE_HEADING = re.compile(
    r"^\s*(?:cl[aá]usula\s+\w+|art[ií]culo\s+\w+|clause\s+\w+|section\s+\w+|\d{1,2}(?:\.\d{1,2})*[.)-])\s*[-.:]?\s*(.{0,120})",
    re.IGNORECASE | re.MULTILINE,
)

_RISK_PATTERNS: dict[str, dict[str, Any]] = {
    "renovacion_automatica": {
        "keywords": ["renovacion automatica", "se renovara automaticamente", "auto-renewal", "automatically renew"],
        "level": "medium",
        "why": "Renovación automática: puede generar compromisos no deseados si no se preavisa.",
    },
    "penalizacion": {
        "keywords": ["penalizacion", "penalidad", "penalty", "interes de demora", "recargo"],
        "level": "high",
        "why": "Penalizaciones económicas explícitas.",
    },
    "indemnizacion": {
        "keywords": ["indemnizar", "indemnizacion", "indemnity", "hold harmless", "mantener indemne"],
        "level": "high",
        "why": "Obligaciones de indemnización que pueden ser asimétricas.",
    },
    "exclusividad": {
        "keywords": ["exclusividad", "en exclusiva", "exclusive", "no competencia", "non-compete"],
        "level": "medium",
        "why": "Cláusulas de exclusividad o no competencia limitan la actividad futura.",
    },
    "limitacion_responsabilidad": {
        "keywords": ["limitacion de responsabilidad", "limitation of liability", "responsabilidad maxima", "en ningun caso respondera"],
        "level": "medium",
        "why": "Limita la responsabilidad de una parte; revisar si es recíproca y su tope.",
    },
    "resolucion_unilateral": {
        "keywords": ["resolver unilateralmente", "terminacion unilateral", "terminate at any time", "sin necesidad de causa"],
        "level": "medium",
        "why": "Permite terminar el contrato unilateralmente.",
    },
    "jurisdiccion": {
        "keywords": ["jurisdiccion", "tribunales de", "ley aplicable", "governing law", "fuero"],
        "level": "low",
        "why": "Define ley aplicable y fuero: relevante si es extranjero.",
    },
    "confidencialidad": {
        "keywords": ["confidencialidad", "confidential", "nda", "no divulgacion", "secreto"],
        "level": "low",
        "why": "Obligaciones de confidencialidad: revisar alcance y duración.",
    },
    "cesion": {
        "keywords": ["cesion del contrato", "ceder el contrato", "assignment", "cesion de derechos"],
        "level": "low",
        "why": "Posibilidad de ceder el contrato a terceros.",
    },
    "propiedad_intelectual": {
        "keywords": ["propiedad intelectual", "intellectual property", "derechos de autor", "titularidad de"],
        "level": "medium",
        "why": "Atribución de titularidad de PI: clave en servicios y desarrollo.",
    },
    "pagos_plazos": {
        "keywords": ["plazo de pago", "forma de pago", "payment terms", "vencimiento", "dias naturales"],
        "level": "low",
        "why": "Condiciones de pago y vencimientos.",
    },
}

_OBLIGATION_MARKERS = ["debera", "se obliga", "se compromete", "estara obligado", "shall", "must", "garantiza"]
_AMBIGUITY_MARKERS = [
    "razonable", "esfuerzos comerciales", "best efforts", "a discrecion", "de buena fe",
    "en su caso", "cuando proceda", "sustancialmente", "aproximadamente",
]


class ReviewContractTextInput(BaseModel):
    text: str = Field(min_length=20, max_length=200000)
    max_items: int = Field(default=15, ge=1, le=40)


class ReviewContractTextTool(BaseTool):
    name = "review_contract_text"
    category = "legal"
    description = (
        "Revisión heurística de un contrato: cláusulas detectadas, patrones de "
        "riesgo, obligaciones y términos ambiguos. No es asesoría legal."
    )
    input_schema = ReviewContractTextInput
    timeout_seconds = 15

    def execute(self, payload: ReviewContractTextInput, ctx: ToolContext) -> dict[str, Any]:
        text = payload.text
        normalized = normalize_for_matching(text)
        sentences = split_sentences(text)

        clauses = [match.group(0).strip()[:140] for match in _CLAUSE_HEADING.finditer(text)]

        risk_hits: list[dict[str, str]] = []
        for risk_id, spec in _RISK_PATTERNS.items():
            for keyword in spec["keywords"]:
                if keyword in normalized:
                    snippet = next(
                        (s for s in sentences if keyword in normalize_for_matching(s)), ""
                    )
                    risk_hits.append(
                        {
                            "risk": risk_id,
                            "level": spec["level"],
                            "why": spec["why"],
                            "snippet": snippet[:300],
                        }
                    )
                    break
            if len(risk_hits) >= payload.max_items:
                break

        obligations = [
            s[:300]
            for s in sentences
            if any(marker in normalize_for_matching(s) for marker in _OBLIGATION_MARKERS)
        ][: payload.max_items]

        ambiguities = [
            {"snippet": s[:300], "marker": marker}
            for s in sentences
            for marker in _AMBIGUITY_MARKERS
            if marker in normalize_for_matching(s)
        ][: payload.max_items]

        return {
            "clauses_detected": clauses[:30],
            "clause_count": len(clauses),
            "risk_hits": risk_hits,
            "obligations": obligations,
            "ambiguities": ambiguities,
            "disclaimer": "Análisis heurístico orientativo; no sustituye asesoría legal profesional.",
        }
