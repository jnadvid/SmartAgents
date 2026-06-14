"""Agente ingeniero de bases de datos."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan, pick_code_text


class DatabaseEngineerAgent(BaseAgent):
    name = "database_engineer"
    display_name = "Ingeniero de Bases de Datos"
    category = "programming"
    description = (
        "Diseña esquemas, modela datos, optimiza consultas e índices y revisa SQL "
        "(rendimiento, normalización, integridad)."
    )
    system_prompt = """
Eres un ingeniero de bases de datos senior (SQL y NoSQL).

Método de trabajo:
- Propón esquemas con tipos, claves, índices y restricciones de integridad.
- Razona la normalización y cuándo desnormalizar por rendimiento.
- Para optimizar consultas, explica el plan esperado y los índices que ayudan.
- Señala riesgos de migración y bloqueos. No inventes el motor si no se indica;
  ofrece la recomendación y sus diferencias (PostgreSQL, MySQL, SQLite…).
""".strip()
    allowed_tools = ["analyze_code_structure", "scan_code_security", "summarize_text"]
    output_format = [
        "Resumen",
        "Modelo de datos / esquema",
        "Índices y rendimiento",
        "Consultas SQL",
        "Integridad y migración",
        "Riesgos",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        code = pick_code_text(ctx)
        if code:
            return [
                ToolInvocationPlan(
                    tool_name="scan_code_security",
                    tool_input={"code": code[:100000], "language": "sql"},
                    reason="Revisar el SQL aportado en busca de inyección y patrones de riesgo.",
                )
            ]
        return []
