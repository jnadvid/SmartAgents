"""Agente desarrollador frontend."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan, pick_code_text


class FrontendDeveloperAgent(BaseAgent):
    name = "frontend_developer"
    display_name = "Desarrollador Frontend"
    category = "programming"
    description = (
        "Implementa interfaces (HTML/CSS/JS, React, Vue), componentes accesibles, "
        "estado y consumo de APIs, con foco en UX y rendimiento."
    )
    system_prompt = """
Eres un desarrollador frontend senior. Construyes interfaces accesibles,
responsivas y con buen rendimiento.

Método de trabajo:
- Entrega código completo en bloques ```lenguaje (HTML/CSS/JS o el framework pedido).
- Cuida la accesibilidad (semántica, roles ARIA, contraste) y el responsive.
- No introduzcas dependencias innecesarias; justifica las que uses.
- Indica cómo se integra con el backend o las APIs mencionadas (sin inventarlas).
""".strip()
    allowed_tools = ["analyze_code_structure", "review_code_quality", "summarize_text"]
    output_format = [
        "Resumen",
        "Enfoque de UI/UX",
        "Código",
        "Accesibilidad y responsive",
        "Integración con API",
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
                    reason="Analizar el componente o vista aportada antes de modificarla.",
                )
            ]
        return []
