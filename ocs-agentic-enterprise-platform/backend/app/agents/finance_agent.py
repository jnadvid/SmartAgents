"""Agente de análisis financiero básico (no es asesoramiento financiero)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan, looks_tabular


class FinanceAgent(BaseAgent):
    name = "finance"
    display_name = "Análisis Financiero"
    category = "finance"
    description = (
        "Analiza costes, presupuestos, facturación, márgenes y escenarios. "
        "Orientativo: no sustituye asesoramiento financiero profesional."
    )
    security_policy = "sensitive"
    system_prompt = """
Eres un analista financiero de gestión (controller) riguroso.

Método de trabajo:
- Las cifras que cites deben proceder del usuario o de la evidencia de la
  herramienta `calculate_basic_financials`; nunca inventes importes.
- Si faltan datos clave (ingresos, costes, horizonte temporal), decláralos
  y no completes con supuestos sin marcarlos como HIPÓTESIS.
- Presenta escenarios (base, pesimista, optimista) cuando haya datos.
- OBLIGATORIO: indica al inicio que el análisis es orientativo y no
  constituye asesoramiento financiero profesional.
""".strip()
    allowed_tools = ["calculate_basic_financials", "analyze_table_text", "summarize_text"]
    output_format = [
        "Resumen financiero",
        "Costes",
        "Ingresos",
        "Margen estimado",
        "Riesgos",
        "Escenarios",
        "Recomendaciones",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        text = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        plans = [
            ToolInvocationPlan(
                tool_name="calculate_basic_financials",
                tool_input={"text": text[:50000]},
                reason="Extraer cifras etiquetadas y calcular margen/escenarios deterministas.",
            )
        ]
        if ctx.extra_context and looks_tabular(ctx.extra_context):
            plans.append(
                ToolInvocationPlan(
                    tool_name="analyze_table_text",
                    tool_input={"text": ctx.extra_context[:200000]},
                    reason="El contexto contiene una tabla: calcular estadísticas por columna.",
                )
            )
        return plans
