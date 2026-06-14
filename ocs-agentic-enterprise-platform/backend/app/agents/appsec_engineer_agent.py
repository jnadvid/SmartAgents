"""Agente de seguridad de aplicaciones (AppSec, defensivo)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan, pick_code_text


class AppSecEngineerAgent(BaseAgent):
    name = "appsec_engineer"
    display_name = "Seguridad de Aplicaciones"
    category = "cybersecurity"
    description = (
        "Revisa la seguridad del código y diseña el SDLC seguro: modelado de "
        "amenazas (STRIDE), análisis SAST heurístico y remediación (OWASP, CWE)."
    )
    security_policy = "sensitive"
    system_prompt = """
Eres un ingeniero de seguridad de aplicaciones (AppSec) defensivo.

Método de trabajo:
- Basa los hallazgos en la evidencia de `scan_code_security` y en el código; cita
  la línea y el CWE. No inventes vulnerabilidades sin respaldo.
- Para cada hallazgo: impacto, explotabilidad (conceptual, sin exploit operativo)
  y remediación concreta con ejemplo de código seguro.
- Cuando proceda, añade un modelado de amenazas STRIDE de alto nivel.
- Enfoque siempre defensivo: hardening y código seguro, nunca payloads ofensivos.
""".strip()
    allowed_tools = ["scan_code_security", "analyze_code_structure", "review_code_quality", "extract_risks"]
    output_format = [
        "Resumen",
        "Hallazgos de seguridad (CWE)",
        "Modelado de amenazas (STRIDE)",
        "Remediación y código seguro",
        "Hardening del SDLC",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        code = pick_code_text(ctx)
        if not code:
            return []
        trimmed = code[:100000]
        return [
            ToolInvocationPlan(
                tool_name="scan_code_security",
                tool_input={"code": trimmed, "language": "auto"},
                reason="Detectar patrones de riesgo (CWE) en el código aportado.",
            ),
            ToolInvocationPlan(
                tool_name="analyze_code_structure",
                tool_input={"code": trimmed, "language": "auto"},
                reason="Contextualizar los hallazgos con la estructura del código.",
            ),
        ]
