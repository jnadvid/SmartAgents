"""Agente jefe de SOC: triaje, decisión de derivación y conclusión final."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan

# Equipos/agentes a los que el jefe de SOC puede derivar (referencia para el prompt).
ROUTING_TARGETS = (
    "incident_responder (respuesta a incidentes / contención)",
    "threat_hunter (caza proactiva)",
    "threat_intel_analyst (inteligencia de amenazas)",
    "vulnerability_triage (gestión de vulnerabilidades)",
    "appsec_engineer (seguridad de aplicaciones)",
    "ot_security_analyst (entornos industriales/OT)",
    "compliance / data_protection_officer (implicaciones regulatorias)",
)


class SocManagerAgent(BaseAgent):
    name = "soc_manager"
    display_name = "Jefe de SOC"
    category = "cybersecurity"
    description = (
        "Lidera el SOC: prioriza la alerta/investigación, DECIDE a qué equipo derivarla "
        "y emite la conclusión final con la decisión (cerrar, escalar, contener)."
    )
    security_policy = "sensitive"
    data_access = ["wazuh_alerts", "local_json"]
    system_prompt = """
Eres el responsable (jefe) de un SOC. Recibes alertas e investigaciones de
los analistas y tu trabajo es DECIDIR.

Método de trabajo:
- HECHOS: solo lo presente en las alertas/evidencia aportada (incluida la de
  la fuente conectada). No inventes IOCs ni atribuciones.
- Prioriza por severidad e impacto en el negocio; marca falsos positivos.
- DECISIÓN DE DERIVACIÓN: indica explícitamente a qué agente/equipo se deriva
  y por qué. Opciones típicas: """ + "; ".join(ROUTING_TARGETS) + """.
- CONCLUSIÓN FINAL: una decisión clara y accionable (cerrar como falso positivo,
  contener, escalar a IR, abrir caso, etc.) con sus siguientes pasos.
- Solo defensa sobre sistemas propios y autorizados.
""".strip()
    allowed_tools = ["map_to_mitre_attack", "extract_risks", "generate_executive_report"]
    output_format = [
        "Resumen del SOC",
        "Alertas priorizadas",
        "Severidad y falsos positivos",
        "Decisión de derivación",
        "Conclusión final",
        "Siguientes pasos",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        combined = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="map_to_mitre_attack",
                tool_input={"text": combined[:100000]},
                reason="Mapear técnicas MITRE candidatas para fundamentar la decisión de derivación.",
            ),
            ToolInvocationPlan(
                tool_name="extract_risks",
                tool_input={"text": combined[:100000]},
                reason="Detectar indicadores de riesgo para priorizar.",
            ),
        ]
