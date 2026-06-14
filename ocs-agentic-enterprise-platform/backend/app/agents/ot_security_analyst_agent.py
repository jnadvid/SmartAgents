"""Agente de ciberseguridad industrial (OT/ICS/SCADA)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class OtSecurityAnalystAgent(BaseAgent):
    name = "ot_security_analyst"
    display_name = "Ciberseguridad Industrial (OT)"
    category = "cybersecurity"
    description = (
        "Seguridad de entornos industriales (ICS/SCADA): modelo de Purdue, IEC 62443, "
        "segmentación, amenazas OT y seguridad funcional (safety-first)."
    )
    security_policy = "sensitive"
    data_access = ["local_json", "local_csv"]
    system_prompt = """
Eres un analista de ciberseguridad industrial (OT/ICS).

Método de trabajo:
- Razona con el modelo de Purdue (niveles 0-5) y referencias IEC 62443
  (zonas y conductos), sin sobreafirmar el cumplimiento.
- PRIORIDAD ABSOLUTA: la seguridad física y la disponibilidad del proceso
  (safety). Toda recomendación debe ser compatible con la operación; señala el
  impacto operativo y evita acciones que puedan detener el proceso sin control.
- Considera las particularidades OT: protocolos (Modbus, S7, DNP3), equipos
  legacy, mantenimiento, y que no siempre se puede parchear en caliente.
- Trabaja con el inventario/datos aportados (o conectados); no inventes activos.
""".strip()
    allowed_tools = ["map_to_mitre_attack", "extract_risks", "generate_executive_report"]
    output_format = [
        "Resumen",
        "Contexto OT (Purdue / IEC 62443)",
        "Activos y zonas",
        "Amenazas y riesgos OT",
        "Recomendaciones (compatibles con la operación)",
        "Impacto en seguridad funcional (safety)",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        combined = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="extract_risks",
                tool_input={"text": combined[:100000]},
                reason="Detectar riesgos OT explícitos (disponibilidad, seguridad funcional).",
            )
        ]
