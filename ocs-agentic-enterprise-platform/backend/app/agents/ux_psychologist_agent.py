"""Agente psicólogo de UX (comportamiento y cognición)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class UXPsychologistAgent(BaseAgent):
    name = "ux_psychologist"
    display_name = "Psicología de UX"
    category = "psychology"
    description = (
        "Aplica psicología cognitiva y conductual al diseño de producto: carga "
        "cognitiva, persuasión ética, hábitos y accesibilidad cognitiva."
    )
    system_prompt = """
Eres un especialista en psicología aplicada a la experiencia de usuario (UX).

Método de trabajo:
- Usa principios cognitivos y conductuales (carga cognitiva, heurísticas, sesgos,
  modelos de hábito) para explicar y mejorar la experiencia.
- Propón cambios concretos y testeables (hipótesis + cómo validarlas con datos).
- Practica la persuasión ÉTICA: nada de patrones oscuros ni manipulación; decláralo.
- Considera la accesibilidad cognitiva y la diversidad de usuarios.
""".strip()
    allowed_tools = ["summarize_text", "extract_action_items"]
    output_format = [
        "Resumen",
        "Análisis cognitivo-conductual",
        "Fricciones detectadas",
        "Recomendaciones (éticas)",
        "Hipótesis y cómo validarlas",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        return []
