"""Agente asistente de negocio generalista."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class BusinessAssistantAgent(BaseAgent):
    name = "business_assistant"
    display_name = "Asistente de Negocio"
    category = "business"
    description = (
        "Tareas generales de negocio: organización, análisis, planificación, "
        "toma de decisiones y productividad."
    )
    system_prompt = """
Eres un consultor de negocio senior, pragmático y orientado a la acción.
Ayudas con organización, análisis de situaciones, comparación de opciones,
toma de decisiones y productividad empresarial.

Método de trabajo:
- Parte solo de la información proporcionada por el usuario y la evidencia.
- Plantea opciones realistas con pros y contras antes de recomendar.
- La recomendación debe ser una sola, clara y justificada.
- Los próximos pasos deben ser accionables (quién/qué/cuándo si es posible).
""".strip()
    allowed_tools = ["summarize_text", "extract_action_items", "extract_risks"]
    output_format = [
        "Resumen",
        "Análisis",
        "Opciones",
        "Recomendación",
        "Próximos pasos",
        "Riesgos",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        plans: list[ToolInvocationPlan] = []
        full_text = f"{ctx.task}\n{ctx.extra_context or ''}"
        if len(full_text) > 1500:
            plans.append(
                ToolInvocationPlan(
                    tool_name="summarize_text",
                    tool_input={"text": full_text[:100000]},
                    reason="La entrada es extensa: obtener frases clave y métricas verificables.",
                )
            )
        plans.append(
            ToolInvocationPlan(
                tool_name="extract_action_items",
                tool_input={"text": full_text[:100000]},
                reason="Detectar acciones pendientes explícitas mencionadas en la tarea.",
            )
        )
        return plans
