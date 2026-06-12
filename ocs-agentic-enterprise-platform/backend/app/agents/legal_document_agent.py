"""Agente de revisión de documentos legales (no sustituye asesoría legal)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class LegalDocumentAgent(BaseAgent):
    name = "legal_document"
    display_name = "Revisor Legal"
    category = "legal"
    description = (
        "Revisa contratos, cláusulas, términos, riesgos y obligaciones. "
        "Orientativo: no sustituye asesoría legal profesional."
    )
    security_policy = "sensitive"
    system_prompt = """
Eres un analista de documentos legales meticuloso. Revisas contratos,
términos y cláusulas para detectar riesgos, obligaciones y ambigüedades.

Método de trabajo:
- Apóyate en la evidencia de la herramienta `review_contract_text` y en el
  texto aportado; cita literalmente las cláusulas relevantes (entre comillas).
- Señala asimetrías entre las partes y plazos/preavisos críticos.
- Marca como ambiguo todo término indeterminado ("razonable", "a discreción").
- OBLIGATORIO: tu respuesta debe empezar indicando que es un análisis
  orientativo y que no sustituye asesoría legal profesional.
""".strip()
    allowed_tools = ["review_contract_text", "extract_risks", "summarize_text"]
    output_format = [
        "Resumen",
        "Cláusulas relevantes",
        "Riesgos",
        "Obligaciones",
        "Puntos ambiguos",
        "Recomendaciones",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        text = f"{ctx.task}\n\n{ctx.extra_context or ''}".strip()
        plans = [
            ToolInvocationPlan(
                tool_name="review_contract_text",
                tool_input={"text": text[:200000]},
                reason="Detectar cláusulas, patrones de riesgo y obligaciones de forma determinista.",
            )
        ]
        if len(text) > 2000:
            plans.append(
                ToolInvocationPlan(
                    tool_name="extract_risks",
                    tool_input={"text": text[:100000]},
                    reason="Texto extenso: localizar frases con indicadores de riesgo adicionales.",
                )
            )
        return plans
