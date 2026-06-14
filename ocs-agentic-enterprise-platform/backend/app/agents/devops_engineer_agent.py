"""Agente ingeniero DevOps / plataforma."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class DevOpsEngineerAgent(BaseAgent):
    name = "devops_engineer"
    display_name = "Ingeniero DevOps"
    category = "programming"
    description = (
        "Diseña CI/CD, contenedores, infraestructura como código y observabilidad. "
        "Entrega configuración concreta (YAML/Dockerfile) y buenas prácticas."
    )
    system_prompt = """
Eres un ingeniero DevOps/Plataforma senior.

Método de trabajo:
- Entrega configuración concreta (pipelines CI/CD, Dockerfile, IaC) en bloques de código.
- Prioriza reproducibilidad, seguridad de la cadena de suministro y mínimos privilegios.
- Incluye estrategia de despliegue (azul/verde, canary), rollback y observabilidad.
- No asumas un proveedor cloud concreto si no se indica; ofrece la opción y sus límites.
- No incluyas secretos reales: usa variables y gestores de secretos.
""".strip()
    allowed_tools = ["extract_action_items", "extract_risks", "summarize_text"]
    output_format = [
        "Resumen",
        "Pipeline CI/CD",
        "Contenedores e infraestructura",
        "Despliegue y rollback",
        "Observabilidad y seguridad",
        "Riesgos",
        "Próximos pasos",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        return [
            ToolInvocationPlan(
                tool_name="extract_action_items",
                tool_input={"text": f"{ctx.task}\n{ctx.extra_context or ''}"[:100000]},
                reason="Detectar acciones y requisitos de automatización mencionados.",
            )
        ]
