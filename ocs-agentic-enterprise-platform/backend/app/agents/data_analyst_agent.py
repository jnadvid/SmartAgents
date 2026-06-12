"""Agente analista de datos sobre texto tabular pegado por el usuario."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan, looks_tabular


class DataAnalystAgent(BaseAgent):
    name = "data_analyst"
    display_name = "Analista de Datos"
    category = "data"
    description = (
        "Analiza datos pegados por el usuario (CSV, TSV, tablas): patrones, "
        "anomalías, KPIs y conclusiones."
    )
    system_prompt = """
Eres un analista de datos riguroso. Trabajas con los datos que el usuario
pega (CSV/tabla) y con las estadísticas deterministas calculadas por la
herramienta local `analyze_table_text`.

Método de trabajo:
- Los números que cites deben proceder de la evidencia de la herramienta o
  del propio texto; no recalcules de cabeza si ya hay evidencia.
- Distingue correlación de causalidad; las causas propuestas son HIPÓTESIS.
- Si los datos son insuficientes o ambiguos (pocas filas, columnas sin
  unidades, valores faltantes), decláralo en "Limitaciones".
""".strip()
    allowed_tools = ["analyze_table_text", "summarize_text"]
    output_format = [
        "Resumen de datos",
        "Patrones detectados",
        "Anomalías",
        "KPIs",
        "Conclusiones",
        "Recomendaciones",
        "Limitaciones",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        candidate = ctx.extra_context if ctx.extra_context and looks_tabular(ctx.extra_context) else ctx.task
        if looks_tabular(candidate):
            return [
                ToolInvocationPlan(
                    tool_name="analyze_table_text",
                    tool_input={"text": candidate[:200000]},
                    reason="Se detectó contenido tabular: calcular estadísticas y anomalías deterministas.",
                )
            ]
        return [
            ToolInvocationPlan(
                tool_name="summarize_text",
                tool_input={"text": f"{ctx.task}\n{ctx.extra_context or ''}"[:100000]},
                reason="No se detectó tabla clara: extraer métricas básicas del texto aportado.",
            )
        ]
