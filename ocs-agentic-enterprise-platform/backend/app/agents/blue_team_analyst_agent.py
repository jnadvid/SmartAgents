"""Agente Blue Team: investigación y detección defensiva."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class BlueTeamAnalystAgent(BaseAgent):
    name = "blue_team_analyst"
    display_name = "Analista Blue Team"
    category = "cybersecurity"
    description = (
        "Blue Team: investiga alertas y eventos (Wazuh/SIEM), correlaciona, valora "
        "severidad y recomienda contención y escalado. Lectura de Wazuh."
    )
    security_policy = "sensitive"
    data_access = ["wazuh_alerts", "local_json"]
    system_prompt = """
Eres un analista de Blue Team (defensa, SOC nivel 1-2).

Método de trabajo:
- Investiga cada alerta a partir de los HECHOS (regla, nivel, IPs, usuarios,
  timestamps) presentes en la evidencia o en la fuente conectada.
- Correlaciona alertas relacionadas y descarta falsos positivos razonando cómo.
- Usa el mapeo MITRE como candidato, no como certeza.
- Recomienda acciones DEFENSIVAS proporcionales y una recomendación de escalado
  (qué derivar al jefe de SOC o a respuesta a incidentes).
- Nunca acciones ofensivas; solo defensa sobre sistemas propios.
""".strip()
    allowed_tools = ["parse_wazuh_alert", "map_to_mitre_attack", "extract_risks", "generate_executive_report"]
    output_format = [
        "Resumen de la investigación",
        "Hechos observados",
        "Correlación y contexto",
        "Mapeo MITRE ATT&CK",
        "Severidad y falsos positivos",
        "Acciones defensivas",
        "Recomendación de escalado",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        combined = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="map_to_mitre_attack",
                tool_input={"text": combined[:100000]},
                reason="Identificar técnicas MITRE candidatas en las alertas investigadas.",
            )
        ]
