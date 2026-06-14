"""Agente revisor de código."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan, pick_code_text


class CodeReviewerAgent(BaseAgent):
    name = "code_reviewer"
    display_name = "Revisor de Código"
    category = "programming"
    description = (
        "Revisa código en busca de bugs, malos olores, complejidad y problemas de "
        "mantenibilidad, con hallazgos priorizados y sugerencias concretas."
    )
    system_prompt = """
Eres un revisor de código exigente y constructivo.

Método de trabajo:
- Basa los hallazgos en la evidencia de las herramientas (estructura, calidad) y
  en el propio código; cita la línea cuando sea posible.
- Clasifica por severidad (bloqueante / mayor / menor / nit) y prioriza.
- Para cada hallazgo, propón una corrección concreta, no solo el problema.
- Reconoce también lo que está bien hecho. No inventes defectos sin respaldo.
""".strip()
    allowed_tools = ["review_code_quality", "analyze_code_structure", "scan_code_security", "extract_code_todos"]
    output_format = [
        "Resumen",
        "Hallazgos bloqueantes",
        "Hallazgos mayores",
        "Hallazgos menores y nits",
        "Aspectos positivos",
        "Sugerencias priorizadas",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        code = pick_code_text(ctx)
        if not code:
            return []
        trimmed = code[:100000]
        return [
            ToolInvocationPlan(
                tool_name="review_code_quality",
                tool_input={"code": trimmed, "language": "auto"},
                reason="Obtener hallazgos de calidad/mantenibilidad con número de línea.",
            ),
            ToolInvocationPlan(
                tool_name="analyze_code_structure",
                tool_input={"code": trimmed, "language": "auto"},
                reason="Medir complejidad y estructura para priorizar la revisión.",
            ),
        ]
