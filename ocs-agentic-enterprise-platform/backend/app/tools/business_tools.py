"""Herramientas de negocio: riesgos y clasificación de solicitudes de clientes."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.security.sanitization import normalize_for_matching
from app.tools._text_utils import split_sentences
from app.tools.base import BaseTool, ToolContext

# ---------------------------------------------------------------------------
# extract_risks
# ---------------------------------------------------------------------------

_RISK_KEYWORDS: dict[str, list[str]] = {
    "high": [
        "multa", "sancion", "incumplimiento", "breach", "brecha", "perdida de datos",
        "impago", "insolvencia", "demanda", "litigio", "vulnerabilidad critica",
        "fuga", "ransomware", "parada de produccion", "single point of failure",
    ],
    "medium": [
        "riesgo", "retraso", "sobrecoste", "dependencia", "deuda", "rotacion",
        "downtime", "obsolescencia", "penalizacion", "exposicion", "conflicto",
        "perdida", "vulnerabilidad", "incidencia", "queja",
    ],
    "low": [
        "incertidumbre", "pendiente", "sin definir", "ambiguo", "falta de",
        "limitacion", "supuesto", "asuncion", "duda",
    ],
}


class ExtractRisksInput(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    max_risks: int = Field(default=20, ge=1, le=50)


class ExtractRisksTool(BaseTool):
    name = "extract_risks"
    category = "business"
    description = (
        "Detecta frases con indicadores de riesgo (operativo, legal, financiero, "
        "técnico) y las clasifica por severidad aproximada."
    )
    input_schema = ExtractRisksInput
    timeout_seconds = 10

    def execute(self, payload: ExtractRisksInput, ctx: ToolContext) -> dict[str, Any]:
        risks: list[dict[str, str]] = []
        for sentence in split_sentences(payload.text):
            normalized = normalize_for_matching(sentence)
            matched_level: str | None = None
            matched_keyword = ""
            for level in ("high", "medium", "low"):
                for keyword in _RISK_KEYWORDS[level]:
                    if keyword in normalized:
                        matched_level, matched_keyword = level, keyword
                        break
                if matched_level:
                    break
            if matched_level:
                risks.append(
                    {"snippet": sentence[:300], "level": matched_level, "keyword": matched_keyword}
                )
            if len(risks) >= payload.max_risks:
                break

        by_level = {level: sum(1 for r in risks if r["level"] == level) for level in ("high", "medium", "low")}
        return {"risks": risks, "count": len(risks), "by_level": by_level}


# ---------------------------------------------------------------------------
# classify_customer_request
# ---------------------------------------------------------------------------

_REQUEST_CATEGORIES: dict[str, list[str]] = {
    "reclamacion": ["queja", "reclamacion", "indignado", "inaceptable", "decepcionado", "complaint", "devolucion", "reembolso"],
    "incidencia_tecnica": ["error", "fallo", "no funciona", "caido", "bug", "bloqueado", "incident", "no puedo acceder", "pantalla"],
    "facturacion": ["factura", "cobro", "cargo", "pago", "billing", "precio", "tarifa", "suscripcion"],
    "solicitud_funcionalidad": ["seria genial", "podriais anadir", "feature", "mejora", "sugerencia", "me gustaria que"],
    "baja_cancelacion": ["baja", "cancelar", "cancelacion", "dar de baja", "unsubscribe", "rescindir"],
    "consulta": ["como", "cuando", "donde", "duda", "pregunta", "informacion", "saber si"],
}

_URGENCY_MARKERS = ["urgente", "inmediato", "critico", "cuanto antes", "hoy mismo", "asap", "ya", "emergencia"]
_NEGATIVE_MARKERS = ["indignado", "harto", "inaceptable", "pesimo", "horrible", "nunca mas", "decepcion", "enfadado", "molesto"]


class ClassifyCustomerRequestInput(BaseModel):
    text: str = Field(min_length=1, max_length=50000)


class ClassifyCustomerRequestTool(BaseTool):
    name = "classify_customer_request"
    category = "business"
    description = (
        "Clasifica una consulta de cliente (reclamación, incidencia, facturación, "
        "funcionalidad, baja, consulta), estima urgencia y tono."
    )
    input_schema = ClassifyCustomerRequestInput
    timeout_seconds = 10

    def execute(self, payload: ClassifyCustomerRequestInput, ctx: ToolContext) -> dict[str, Any]:
        normalized = normalize_for_matching(payload.text)

        scores: dict[str, int] = {}
        matched: dict[str, list[str]] = {}
        for category, keywords in _REQUEST_CATEGORIES.items():
            hits = [kw for kw in keywords if kw in normalized]
            if hits:
                scores[category] = len(hits)
                matched[category] = hits

        if scores:
            best_category = max(scores, key=lambda c: scores[c])
        else:
            best_category = "consulta"

        urgency_hits = [m for m in _URGENCY_MARKERS if m in normalized]
        negative_hits = [m for m in _NEGATIVE_MARKERS if m in normalized]
        urgency = "alta" if urgency_hits or best_category == "reclamacion" else "media" if best_category == "incidencia_tecnica" else "normal"

        return {
            "category": best_category,
            "category_scores": scores,
            "matched_keywords": matched.get(best_category, []),
            "urgency": urgency,
            "urgency_markers": urgency_hits,
            "tone": "negativo" if negative_hits else "neutro",
            "negative_markers": negative_hits,
        }
