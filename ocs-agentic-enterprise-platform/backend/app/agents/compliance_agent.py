"""Agente de cumplimiento normativo (gap analysis orientativo)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan
from app.security.sanitization import normalize_for_matching


class ComplianceAgent(BaseAgent):
    name = "compliance"
    display_name = "Cumplimiento Normativo"
    category = "compliance"
    description = (
        "Evalúa cumplimiento frente a marcos como ISO 27001 o RGPD y propone "
        "planes de remediación. No sustituye una auditoría formal."
    )
    security_policy = "sensitive"
    system_prompt = """
Eres un consultor de cumplimiento normativo (ISO 27001, RGPD, ENS, NIS2).

Método de trabajo:
- Basa las brechas en la evidencia de la herramienta
  `generate_compliance_gap` y en lo descrito por el usuario; si un control
  no se menciona, está "sin evidencia", no necesariamente incumplido:
  distingue ambos casos.
- El plan de remediación debe priorizar por riesgo y esfuerzo (quick wins
  primero) e indicar evidencias documentales necesarias para auditoría.
- Si el marco normativo no está claro en la tarea, decláralo y analiza
  contra el más probable, justificándolo.
- OBLIGATORIO: indica que es una evaluación orientativa sobre un
  subconjunto de controles y no sustituye una auditoría formal.
""".strip()
    allowed_tools = ["generate_compliance_gap", "extract_risks", "summarize_text", "generate_executive_report"]
    output_format = [
        "Resumen",
        "Marco aplicable",
        "Brechas identificadas",
        "Riesgos",
        "Plan de remediación",
        "Evidencias requeridas",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        text = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        normalized = normalize_for_matching(text)
        framework = "gdpr" if any(k in normalized for k in ("gdpr", "rgpd", "proteccion de datos")) else "iso27001"
        return [
            ToolInvocationPlan(
                tool_name="generate_compliance_gap",
                tool_input={"framework": framework, "implemented_controls_text": text[:100000]},
                reason=f"Gap analysis determinista contra el marco '{framework}'.",
            )
        ]
