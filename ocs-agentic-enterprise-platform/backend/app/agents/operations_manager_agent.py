"""Agente de operaciones y mejora de procesos."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class OperationsManagerAgent(BaseAgent):
    name = "operations_manager"
    display_name = "Gestión de Operaciones"
    category = "business"
    description = (
        "Optimiza procesos y operaciones: cuellos de botella, eficiencia, SOPs y "
        "mejora continua (Lean, teoría de restricciones)."
    )
    system_prompt = """
Eres un responsable de operaciones experto en mejora de procesos (Lean, Six
Sigma ligero, teoría de restricciones).

Método de trabajo:
- Mapea el proceso actual (AS-IS) a partir de lo descrito; identifica desperdicios
  y cuellos de botella.
- Propón el proceso objetivo (TO-BE) con pasos, responsables y métricas (lead time,
  throughput, tasa de error).
- Prioriza mejoras por impacto/esfuerzo y define cómo medir el resultado.
- No inventes cifras: si faltan, indícalo y propón cómo instrumentarlas.
""".strip()
    allowed_tools = ["extract_action_items", "extract_risks", "summarize_text"]
    output_format = [
        "Resumen",
        "Proceso actual (AS-IS)",
        "Cuellos de botella y desperdicios",
        "Proceso objetivo (TO-BE)",
        "Métricas y seguimiento",
        "Plan de mejora priorizado",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        return [
            ToolInvocationPlan(
                tool_name="extract_action_items",
                tool_input={"text": f"{ctx.task}\n{ctx.extra_context or ''}"[:100000]},
                reason="Detectar acciones de mejora explícitas en la descripción del proceso.",
            )
        ]
