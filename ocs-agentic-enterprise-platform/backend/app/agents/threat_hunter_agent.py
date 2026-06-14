"""Agente Threat Hunter: caza proactiva de amenazas (hipótesis)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class ThreatHunterAgent(BaseAgent):
    name = "threat_hunter"
    display_name = "Threat Hunter"
    category = "cybersecurity"
    description = (
        "Caza proactiva de amenazas: formula hipótesis, define qué buscar y propone "
        "consultas/lógica de detección sobre los datos disponibles."
    )
    security_policy = "sensitive"
    data_access = ["wazuh_alerts", "local_json"]
    system_prompt = """
Eres un threat hunter. Buscas señales de actividad maliciosa que las reglas no
detectan, partiendo de hipótesis basadas en MITRE ATT&CK.

Método de trabajo:
- Formula HIPÓTESIS de caza concretas (p. ej. "posible persistencia vía tarea
  programada") y vincúlalas a técnicas MITRE.
- Para cada hipótesis indica QUÉ datos mirar y qué patrón confirmaría/descartaría.
- Si hay datos conectados, razona solo sobre lo presente; no inventes resultados.
- Propón lógica de detección (pseudo-consulta) y cómo reducir falsos positivos.
- Solo defensa y observación sobre sistemas propios.
""".strip()
    allowed_tools = ["map_to_mitre_attack", "extract_risks", "summarize_text"]
    output_format = [
        "Resumen",
        "Hipótesis de caza",
        "Técnicas MITRE asociadas",
        "Qué buscar (datos y patrones)",
        "Lógica de detección propuesta",
        "Hallazgos sobre los datos disponibles",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        combined = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="map_to_mitre_attack",
                tool_input={"text": combined[:100000]},
                reason="Anclar las hipótesis de caza a técnicas MITRE ATT&CK.",
            )
        ]
