"""Agente de inteligencia de amenazas (CTI)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class ThreatIntelAnalystAgent(BaseAgent):
    name = "threat_intel_analyst"
    display_name = "Inteligencia de Amenazas"
    category = "cybersecurity"
    description = (
        "Analiza inteligencia de amenazas (CTI): actores, TTPs, IOCs y campañas, "
        "a partir de la información aportada. No navega por Internet."
    )
    security_policy = "sensitive"
    data_access = ["wazuh_alerts", "local_json"]
    system_prompt = """
Eres un analista de inteligencia de amenazas (CTI).

Método de trabajo:
- Trabajas SOLO con la información aportada por el usuario; no tienes acceso a
  fuentes externas ni feeds en vivo, y debes declararlo.
- Estructura el análisis con el Diamond Model y MITRE ATT&CK (como candidatos).
- Lista IOCs (IPs, hashes, dominios, URLs) solo si aparecen en la evidencia.
- Distingue atribución especulativa (HIPÓTESIS) de hechos observados.
- Propón acciones defensivas: detección, hunting y priorización.
""".strip()
    allowed_tools = ["map_to_mitre_attack", "extract_risks", "summarize_text"]
    output_format = [
        "Resumen",
        "Actor y motivación (hipótesis)",
        "TTPs (MITRE ATT&CK)",
        "IOCs observados",
        "Detección y hunting",
        "Recomendaciones defensivas",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        combined = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="map_to_mitre_attack",
                tool_input={"text": combined[:100000]},
                reason="Mapear TTPs candidatas a partir de la descripción aportada.",
            )
        ]
