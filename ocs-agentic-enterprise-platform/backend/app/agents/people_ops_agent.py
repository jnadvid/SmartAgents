"""Agente de People Ops (gestión de personas)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class PeopleOpsAgent(BaseAgent):
    name = "people_ops"
    display_name = "People Ops"
    category = "hr"
    description = (
        "Gestión de personas: evaluación del desempeño, planes de carrera, "
        "políticas internas, retención y feedback, de forma justa y consistente."
    )
    system_prompt = """
Eres responsable de People Operations.

Método de trabajo:
- Diseña marcos de desempeño y feedback objetivos, basados en comportamientos y
  resultados observables, no en rasgos de personalidad.
- Propón políticas internas claras, consistentes y conformes con buenas prácticas
  laborales (sin sustituir asesoría legal).
- Cuida la equidad, la transparencia y la protección de datos del personal.
- No inventes datos de empleados; trabaja con lo aportado y declara lo que falte.
""".strip()
    allowed_tools = ["summarize_text", "extract_action_items", "extract_risks"]
    output_format = [
        "Resumen",
        "Diagnóstico",
        "Propuesta (política/marco)",
        "Plan de implantación",
        "Equidad y protección de datos",
        "Riesgos",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        return [
            ToolInvocationPlan(
                tool_name="extract_action_items",
                tool_input={"text": f"{ctx.task}\n{ctx.extra_context or ''}"[:100000]},
                reason="Detectar acciones y compromisos explícitos sobre personas.",
            )
        ]
