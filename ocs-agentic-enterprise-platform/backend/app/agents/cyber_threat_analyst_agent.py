"""Agente analista de amenazas (SOC nivel 2, defensivo)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


def _looks_like_wazuh_json(text: str) -> bool:
    stripped = (text or "").strip()
    return stripped.startswith("{") and ('"rule"' in stripped or "'rule'" in stripped)


class CyberThreatAnalystAgent(BaseAgent):
    name = "cyber_threat_analyst"
    display_name = "Analista de Amenazas"
    category = "cybersecurity"
    description = (
        "Analiza alertas de seguridad (Wazuh/SIEM), eventos sospechosos e "
        "incidentes desde una perspectiva defensiva."
    )
    security_policy = "sensitive"
    system_prompt = """
Eres un analista de ciberseguridad defensiva (SOC nivel 2). Analizas
alertas SIEM (especialmente Wazuh), eventos y descripciones de incidentes
para ayudar a defender sistemas propios y autorizados.

Método de trabajo:
- HECHOS: solo lo presente en la alerta/evidencia (regla, nivel, IPs,
  usuarios, timestamps). Cita los campos exactos.
- HIPÓTESIS: posibles explicaciones (incluye siempre la posibilidad de
  falso positivo y cómo descartarla).
- Usa el mapeo MITRE de la herramienta como candidato, no como certeza.
- Acciones recomendadas: contención, investigación adicional y
  recolección de evidencias, proporcionales a la severidad.
- NUNCA propongas acciones ofensivas ni represalias; solo defensa,
  detección y respuesta sobre sistemas propios.
- Lista los IOCs observados (IPs, hashes, usuarios, rutas) solo si
  aparecen en la evidencia.
""".strip()
    allowed_tools = ["parse_wazuh_alert", "map_to_mitre_attack", "extract_risks", "generate_executive_report"]
    output_format = [
        "Resumen",
        "Hechos observados",
        "Hipótesis",
        "Mapeo MITRE ATT&CK",
        "Severidad",
        "IOCs",
        "Acciones recomendadas",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        combined = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        plans: list[ToolInvocationPlan] = []

        json_candidate = None
        for candidate in (ctx.extra_context or "", ctx.task):
            if _looks_like_wazuh_json(candidate):
                json_candidate = candidate.strip()
                break
        if json_candidate:
            plans.append(
                ToolInvocationPlan(
                    tool_name="parse_wazuh_alert",
                    tool_input={"alert": json_candidate[:100000]},
                    reason="La entrada parece una alerta Wazuh en JSON: normalizar campos.",
                )
            )
        plans.append(
            ToolInvocationPlan(
                tool_name="map_to_mitre_attack",
                tool_input={"text": combined[:100000]},
                reason="Buscar técnicas MITRE ATT&CK candidatas según el contenido del evento.",
            )
        )
        return plans
