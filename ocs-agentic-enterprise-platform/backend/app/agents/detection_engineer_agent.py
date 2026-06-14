"""Agente de ingeniería de detección (reglas SIEM / Sigma)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class DetectionEngineerAgent(BaseAgent):
    name = "detection_engineer"
    display_name = "Ingeniero de Detección"
    category = "cybersecurity"
    description = (
        "Diseña casos de uso y reglas de detección (Sigma, lógica SIEM/Wazuh) a partir "
        "de TTPs, con foco en cobertura MITRE y control de falsos positivos."
    )
    security_policy = "sensitive"
    data_access = ["wazuh_alerts", "local_json"]
    system_prompt = """
Eres un ingeniero de detección (detection engineering).

Método de trabajo:
- Parte de la amenaza/TTP a cubrir y propón una regla de detección concreta
  (formato Sigma o lógica SIEM/Wazuh) con su lógica explicada.
- Indica la fuente de logs necesaria, la cobertura MITRE y los supuestos.
- Estima y mitiga falsos positivos; define umbrales y excepciones.
- No afirmes que una regla detecta algo que su lógica no cubre.
""".strip()
    allowed_tools = ["map_to_mitre_attack", "extract_risks", "summarize_text"]
    output_format = [
        "Resumen",
        "Amenaza a detectar (MITRE)",
        "Fuentes de logs requeridas",
        "Regla de detección propuesta",
        "Falsos positivos y umbrales",
        "Validación y cobertura",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        combined = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="map_to_mitre_attack",
                tool_input={"text": combined[:100000]},
                reason="Determinar las técnicas MITRE que la detección debe cubrir.",
            )
        ]
