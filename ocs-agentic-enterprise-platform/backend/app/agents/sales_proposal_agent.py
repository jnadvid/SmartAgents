"""Agente de propuestas comerciales y materiales de venta."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class SalesProposalAgent(BaseAgent):
    name = "sales_proposal"
    display_name = "Propuestas Comerciales"
    category = "sales"
    description = (
        "Crea propuestas comerciales, ofertas, argumentarios, emails de venta "
        "y análisis de oportunidades."
    )
    system_prompt = """
Eres un consultor comercial senior especializado en propuestas B2B.

Método de trabajo:
- Parte de la necesidad real del cliente descrita en la tarea; si no está
  clara, decláralo y formula la necesidad detectada como hipótesis.
- La propuesta debe ser concreta: alcance delimitado, entregables
  verificables y próximos pasos con acción y plazo.
- No inventes precios, plazos ni referencias de clientes: usa marcadores
  [COMPLETAR: dato] cuando falte información comercial.
- Usa el esqueleto de la herramienta `create_sales_proposal` como guía de
  estructura, adaptándolo al caso.
""".strip()
    allowed_tools = ["create_sales_proposal", "summarize_text", "extract_action_items"]
    output_format = [
        "Propuesta",
        "Necesidad detectada",
        "Solución propuesta",
        "Alcance",
        "Entregables",
        "Diferenciadores",
        "Próximos pasos",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        need = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="create_sales_proposal",
                tool_input={"need": need[:20000]},
                reason="Generar esqueleto estructurado y checklist de la propuesta.",
            )
        ]
