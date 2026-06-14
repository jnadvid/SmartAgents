"""Agente de respuesta a incidentes (DFIR defensivo)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class IncidentResponderAgent(BaseAgent):
    name = "incident_responder"
    display_name = "Respuesta a Incidentes"
    category = "cybersecurity"
    description = (
        "Coordina la respuesta a incidentes (DFIR): contención, erradicación, "
        "recuperación y lecciones aprendidas, sobre sistemas propios y autorizados."
    )
    security_policy = "sensitive"
    system_prompt = """
Eres un responder de incidentes (DFIR) defensivo, siguiendo el ciclo
NIST/SANS: preparación, detección, contención, erradicación, recuperación
y lecciones aprendidas.

Método de trabajo:
- HECHOS: solo lo presente en la evidencia (alertas, logs, IOCs aportados).
- Propón pasos de contención proporcionales y reversibles; prioriza preservar evidencia.
- Define qué evidencia recolectar y la cadena de custodia.
- Acciones SIEMPRE defensivas y sobre activos propios; nunca contraataques.
- Incluye criterios de escalado y comunicación (interna, legal, regulatoria).
""".strip()
    allowed_tools = ["parse_wazuh_alert", "map_to_mitre_attack", "extract_action_items", "extract_risks"]
    output_format = [
        "Resumen del incidente",
        "Hechos y evidencia",
        "Clasificación y severidad",
        "Contención inmediata",
        "Erradicación y recuperación",
        "Recolección de evidencia",
        "Comunicación y escalado",
        "Lecciones aprendidas",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        combined = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="map_to_mitre_attack",
                tool_input={"text": combined[:100000]},
                reason="Identificar técnicas MITRE ATT&CK candidatas para guiar la contención.",
            ),
            ToolInvocationPlan(
                tool_name="extract_action_items",
                tool_input={"text": combined[:100000]},
                reason="Extraer acciones de respuesta explícitas mencionadas.",
            ),
        ]
