"""Agente arquitecto de software."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan, pick_code_text


class SoftwareArchitectAgent(BaseAgent):
    name = "software_architect"
    display_name = "Arquitecto de Software"
    category = "programming"
    description = (
        "Diseña arquitecturas: componentes, límites, patrones, decisiones técnicas "
        "(ADR), trade-offs de escalabilidad, datos e integración."
    )
    system_prompt = """
Eres un arquitecto de software senior. Diseñas soluciones mantenibles y
proporcionadas al problema, evitando sobre-ingeniería.

Método de trabajo:
- Parte de requisitos y restricciones reales (no inventes requisitos no dados).
- Propón una arquitectura concreta: componentes, responsabilidades y límites.
- Justifica decisiones clave como ADRs: contexto, decisión, alternativas y consecuencias.
- Señala trade-offs (escalabilidad, coste, complejidad, time-to-market) de forma explícita.
- Si analizas código existente, apóyate en la evidencia de las herramientas.
""".strip()
    allowed_tools = ["analyze_code_structure", "summarize_text", "extract_risks"]
    output_format = [
        "Resumen",
        "Requisitos y restricciones",
        "Arquitectura propuesta",
        "Decisiones clave (ADR)",
        "Trade-offs",
        "Riesgos técnicos",
        "Próximos pasos",
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
                    reason="Hay código de partida: analizar estructura para fundamentar la arquitectura.",
                )
            ]
        return []
