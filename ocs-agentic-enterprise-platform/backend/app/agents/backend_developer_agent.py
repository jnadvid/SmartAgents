"""Agente desarrollador backend."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan, pick_code_text


class BackendDeveloperAgent(BaseAgent):
    name = "backend_developer"
    display_name = "Desarrollador Backend"
    category = "programming"
    description = (
        "Implementa lógica de servidor, APIs, modelos de datos e integraciones. "
        "Escribe código idiomático y explica su funcionamiento."
    )
    system_prompt = """
Eres un desarrollador backend senior (Python, Node, Go, Java).

Método de trabajo:
- Escribe código completo y ejecutable en bloques ```lenguaje, no pseudocódigo.
- Sigue las convenciones del lenguaje y maneja errores y casos límite.
- No inventes APIs, librerías ni firmas que no existan; si dudas, decláralo.
- Indica dependencias necesarias y cómo se prueba el código.
- Si revisas código existente, apóyate en la evidencia de las herramientas y
  no afirmes problemas que no estén respaldados por ella.
""".strip()
    allowed_tools = ["analyze_code_structure", "review_code_quality", "extract_action_items"]
    output_format = [
        "Resumen",
        "Enfoque",
        "Código",
        "Explicación",
        "Dependencias y pruebas",
        "Consideraciones",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        code = pick_code_text(ctx)
        if code:
            return [
                ToolInvocationPlan(
                    tool_name="analyze_code_structure",
                    tool_input={"code": code[:100000], "language": "auto"},
                    reason="Analizar el código aportado antes de modificarlo o ampliarlo.",
                )
            ]
        return []
