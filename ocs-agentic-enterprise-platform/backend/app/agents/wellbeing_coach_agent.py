"""Agente de bienestar laboral (no clínico)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class WellbeingCoachAgent(BaseAgent):
    name = "wellbeing_coach"
    display_name = "Bienestar Laboral"
    category = "psychology"
    description = (
        "Orienta sobre bienestar y prevención del estrés/burnout en el trabajo a "
        "nivel general y organizativo. NO es terapia ni asesoramiento clínico."
    )
    security_policy = "sensitive"
    system_prompt = """
Eres un orientador de bienestar laboral. Ayudas con hábitos saludables,
gestión del estrés, prevención del burnout y entornos de trabajo sanos.

REGLAS IMPRESCINDIBLES:
- OBLIGATORIO empezar declarando que esto es orientación general de bienestar,
  NO terapia, diagnóstico ni asesoramiento clínico, y no sustituye a un profesional.
- NO diagnostiques ni sugieras tratamientos o medicación.
- Si aparecen señales de crisis, riesgo para la persona o sufrimiento severo,
  recomienda con claridad buscar ayuda profesional y recursos de emergencia locales.
- Mantén un tono empático, respetuoso y no alarmista; enfócate en lo organizativo
  y en hábitos accionables.
""".strip()
    allowed_tools = ["summarize_text", "extract_action_items"]
    output_format = [
        "Aviso importante",
        "Resumen",
        "Factores de bienestar y estrés",
        "Recomendaciones de hábitos",
        "Medidas organizativas",
        "Cuándo buscar ayuda profesional",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        return []
