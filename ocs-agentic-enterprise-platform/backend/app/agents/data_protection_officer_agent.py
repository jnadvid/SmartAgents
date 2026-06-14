"""Agente delegado de protección de datos (DPO / RGPD)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class DataProtectionOfficerAgent(BaseAgent):
    name = "data_protection_officer"
    display_name = "Protección de Datos (DPO)"
    category = "compliance"
    description = (
        "Protección de datos (RGPD/LOPDGDD): bases de legitimación, derechos, "
        "RAT, análisis de riesgo y EIPD. Orientativo, no es asesoría legal."
    )
    security_policy = "sensitive"
    system_prompt = """
Eres un Delegado de Protección de Datos (DPO) con dominio del RGPD y la
LOPDGDD.

Método de trabajo:
- OBLIGATORIO: indica al inicio que es orientación y no sustituye asesoría jurídica.
- Identifica tratamientos, bases de legitimación, finalidad, minimización y plazos.
- Señala derechos de los interesados y cómo atenderlos.
- Evalúa si procede una EIPD (DPIA) y describe medidas técnicas y organizativas.
- Trabaja con lo aportado; no inventes hechos ni artículos. Cita el marco con cautela.
""".strip()
    allowed_tools = ["generate_compliance_gap", "extract_risks", "summarize_text"]
    output_format = [
        "Aviso (no es asesoría legal)",
        "Resumen",
        "Tratamientos y bases de legitimación",
        "Derechos de los interesados",
        "Riesgos y medidas (técnicas y organizativas)",
        "¿Procede EIPD/DPIA?",
        "Recomendaciones",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        combined = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="generate_compliance_gap",
                tool_input={"framework": "gdpr", "implemented_controls_text": combined[:100000]},
                reason="Estimar brechas frente al RGPD a partir de lo descrito.",
            )
        ]
