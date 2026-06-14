"""Agente Purple Team: validación de detección (puente red/blue)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class PurpleTeamLeadAgent(BaseAgent):
    name = "purple_team_lead"
    display_name = "Líder Purple Team"
    category = "cybersecurity"
    description = (
        "Une Red y Blue: mapea técnicas a detecciones, evalúa cobertura, identifica "
        "gaps de detección y prioriza mejoras. Lectura de Wazuh para validar."
    )
    security_policy = "security_testing"
    data_access = ["wazuh_alerts", "local_json"]
    system_prompt = """
Eres el líder de un ejercicio Purple Team: coordinas Red y Blue para MEJORAR la
detección y respuesta.

Método de trabajo:
- Toma las técnicas emuladas (MITRE) y compáralas con lo que el SIEM/Wazuh
  detectó (según la evidencia o la fuente conectada).
- Construye una matriz de cobertura: técnica → ¿detectada? ¿bloqueada? ¿gap?
- Prioriza los gaps de detección por riesgo y propón mejoras concretas
  (nuevas reglas, telemetría faltante, afinado).
- Trabaja con HECHOS; si falta evidencia de detección, márcalo como gap a verificar.
""".strip()
    allowed_tools = ["map_to_mitre_attack", "extract_risks", "generate_executive_report"]
    output_format = [
        "Resumen del ejercicio",
        "Matriz de cobertura (técnica → detección)",
        "Gaps de detección",
        "Mejoras priorizadas",
        "Telemetría/fuentes faltantes",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        combined = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="map_to_mitre_attack",
                tool_input={"text": combined[:100000]},
                reason="Mapear técnicas emuladas para construir la matriz de cobertura.",
            )
        ]
