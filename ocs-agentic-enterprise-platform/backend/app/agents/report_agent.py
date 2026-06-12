"""Agente generador de informes ejecutivos y técnicos."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class ReportAgent(BaseAgent):
    name = "report"
    display_name = "Generador de Informes"
    category = "reporting"
    description = (
        "Convierte análisis técnicos o datos en informes ejecutivos o "
        "técnicos claros y accionables."
    )
    system_prompt = """
Eres un redactor de informes ejecutivos y técnicos.

Método de trabajo:
- Audiencia por defecto: dirección no técnica. Si la tarea pide informe
  técnico, ajusta el nivel de detalle.
- El resumen ejecutivo debe poder leerse solo: situación, impacto y
  decisión/acción requerida en menos de 10 líneas.
- Cada hallazgo: qué se observó (HECHO), qué significa (HIPÓTESIS/impacto)
  y qué hacer (RECOMENDACIÓN).
- No añadas hallazgos que no estén en el material aportado.
- En "Anexos sugeridos" lista evidencias o detalles que convendría adjuntar.
""".strip()
    allowed_tools = ["summarize_text", "generate_markdown_report", "generate_executive_report", "extract_risks"]
    output_format = [
        "Título",
        "Resumen ejecutivo",
        "Hallazgos",
        "Impacto",
        "Recomendaciones",
        "Anexos sugeridos",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        text = f"{ctx.task}\n{ctx.extra_context or ''}"
        plans: list[ToolInvocationPlan] = []
        if len(text) > 1200:
            plans.append(
                ToolInvocationPlan(
                    tool_name="summarize_text",
                    tool_input={"text": text[:100000], "max_sentences": 8},
                    reason="Extraer frases clave del material fuente para fundamentar el informe.",
                )
            )
            plans.append(
                ToolInvocationPlan(
                    tool_name="extract_risks",
                    tool_input={"text": text[:100000]},
                    reason="Localizar riesgos mencionados en el material para la sección de impacto.",
                )
            )
        return plans
