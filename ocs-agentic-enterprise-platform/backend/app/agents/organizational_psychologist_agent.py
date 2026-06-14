"""Agente psicólogo organizacional / del trabajo."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class OrganizationalPsychologistAgent(BaseAgent):
    name = "organizational_psychologist"
    display_name = "Psicología Organizacional"
    category = "psychology"
    description = (
        "Analiza dinámicas de equipo, motivación, liderazgo, cultura y gestión del "
        "cambio desde la psicología del trabajo. Orientativo, no clínico."
    )
    security_policy = "sensitive"
    system_prompt = """
Eres un psicólogo organizacional y del trabajo (I/O). Ayudas con clima,
motivación, liderazgo, comunicación de equipos y gestión del cambio.

Método de trabajo:
- Fundamenta las recomendaciones en marcos reconocidos (p. ej. motivación
  intrínseca, seguridad psicológica, gestión del cambio) sin sobreafirmar.
- Distingue HECHOS (lo que describe el usuario) de tu interpretación (HIPÓTESIS).
- Propón intervenciones organizativas accionables y medibles.
- Ámbito ORGANIZACIONAL, no clínico: si aparece sufrimiento individual o salud
  mental, recomienda derivar a profesionales o recursos especializados.
""".strip()
    allowed_tools = ["summarize_text", "extract_action_items", "extract_risks"]
    output_format = [
        "Resumen",
        "Análisis (marcos aplicables)",
        "Hipótesis",
        "Intervenciones recomendadas",
        "Indicadores de seguimiento",
        "Riesgos y consideraciones éticas",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        return [
            ToolInvocationPlan(
                tool_name="extract_action_items",
                tool_input={"text": f"{ctx.task}\n{ctx.extra_context or ''}"[:100000]},
                reason="Detectar acciones o compromisos explícitos en la situación descrita.",
            )
        ]
