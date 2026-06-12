"""Agente de soporte y atención a clientes."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class CustomerSupportAgent(BaseAgent):
    name = "customer_support"
    display_name = "Soporte a Clientes"
    category = "customer_support"
    description = (
        "Responde a clientes, clasifica incidencias, redacta respuestas "
        "educadas y gestiona reclamaciones."
    )
    system_prompt = """
Eres un especialista en atención al cliente: empático, resolutivo y claro.

Método de trabajo:
- Usa la clasificación determinista de la herramienta
  `classify_customer_request` (categoría, urgencia, tono) como punto de partida.
- La respuesta sugerida debe: reconocer la situación, responder a lo
  preguntado, indicar el siguiente paso y mantener tono profesional.
- No prometas plazos, compensaciones ni funcionalidades que la tarea no
  autorice: si haría falta, márcalo como acción interna a validar.
- Si faltan datos para resolver (número de pedido, capturas, cuenta),
  pídelos explícitamente en la respuesta sugerida.
""".strip()
    allowed_tools = ["classify_customer_request", "summarize_text"]
    output_format = [
        "Clasificación de consulta",
        "Respuesta sugerida",
        "Tono recomendado",
        "Datos que faltan",
        "Acciones internas",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        text = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="classify_customer_request",
                tool_input={"text": text[:50000]},
                reason="Clasificar la consulta del cliente (categoría, urgencia, tono).",
            )
        ]
