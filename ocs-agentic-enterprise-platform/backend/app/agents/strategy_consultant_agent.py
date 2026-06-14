"""Agente consultor de estrategia."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class StrategyConsultantAgent(BaseAgent):
    name = "strategy_consultant"
    display_name = "Consultor de Estrategia"
    category = "business"
    description = (
        "Estrategia corporativa y competitiva: modelos de negocio, ventaja "
        "competitiva, crecimiento y priorización (frameworks tipo Porter, SWOT, JTBD)."
    )
    system_prompt = """
Eres un consultor de estrategia senior (estilo firma top-tier), estructurado
y orientado a impacto.

Método de trabajo:
- Estructura el problema (MECE) y usa frameworks reconocidos solo cuando aporten.
- Parte de los datos del usuario; cuando falten, declara los supuestos clave.
- Da una recomendación priorizada con impacto/esfuerzo y una hoja de ruta.
- Sé concreto: evita generalidades; cada recomendación debe ser accionable.
""".strip()
    allowed_tools = ["summarize_text", "extract_risks", "extract_action_items"]
    output_format = [
        "Resumen ejecutivo",
        "Diagnóstico",
        "Opciones estratégicas",
        "Recomendación priorizada",
        "Hoja de ruta",
        "Riesgos y supuestos",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        return [
            ToolInvocationPlan(
                tool_name="extract_risks",
                tool_input={"text": f"{ctx.task}\n{ctx.extra_context or ''}"[:100000]},
                reason="Identificar riesgos y supuestos explícitos en la situación.",
            )
        ]
