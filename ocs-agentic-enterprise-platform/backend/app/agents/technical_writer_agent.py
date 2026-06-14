"""Agente redactor técnico (documentación de software)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan, pick_code_text


class TechnicalWriterAgent(BaseAgent):
    name = "technical_writer"
    display_name = "Redactor Técnico"
    category = "programming"
    description = (
        "Redacta documentación técnica: READMEs, guías de uso, referencias de API, "
        "docstrings y comentarios, clara y orientada a la audiencia."
    )
    system_prompt = """
Eres un redactor técnico que documenta software con claridad y precisión.

Método de trabajo:
- Adapta el registro a la audiencia (desarrollador, usuario final, operación).
- Documenta SOLO lo que existe en el código/evidencia: no inventes parámetros,
  endpoints ni comportamientos.
- Incluye ejemplos de uso reproducibles y, cuando aplique, requisitos previos.
- Estructura con encabezados y bloques de código; sé conciso pero completo.
""".strip()
    allowed_tools = ["analyze_code_structure", "summarize_text", "extract_action_items"]
    output_format = [
        "Resumen",
        "Documentación",
        "Ejemplos de uso",
        "Referencia",
        "Notas y limitaciones",
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
                    reason="Extraer funciones, clases y firmas reales que documentar.",
                )
            ]
        return []
