"""Agente ingeniero de QA y testing."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan, pick_code_text


class QATestEngineerAgent(BaseAgent):
    name = "qa_test_engineer"
    display_name = "Ingeniero de QA"
    category = "programming"
    description = (
        "Diseña estrategias de prueba, casos (incluyendo límites y negativos) y "
        "genera esqueletos de tests automatizados a partir del código."
    )
    system_prompt = """
Eres un ingeniero de QA y automatización de pruebas.

Método de trabajo:
- Define una estrategia: niveles (unitario, integración, e2e) y qué cubrir.
- Diseña casos concretos, incluyendo casos límite, negativos y de error.
- Si hay código Python, usa el esqueleto de tests de la herramienta como base y
  complétalo con asserts reales; no afirmes cobertura que no exista.
- Distingue lo verificable de las suposiciones sobre el comportamiento esperado.
""".strip()
    allowed_tools = ["generate_test_skeleton", "analyze_code_structure", "review_code_quality"]
    output_format = [
        "Resumen",
        "Estrategia de pruebas",
        "Casos de prueba",
        "Casos límite y negativos",
        "Esqueleto de tests",
        "Cobertura y riesgos",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        code = pick_code_text(ctx)
        if not code:
            return []
        return [
            ToolInvocationPlan(
                tool_name="generate_test_skeleton",
                tool_input={"code": code[:100000], "framework": "pytest"},
                reason="Generar esqueletos de tests para las funciones públicas detectadas.",
            )
        ]
