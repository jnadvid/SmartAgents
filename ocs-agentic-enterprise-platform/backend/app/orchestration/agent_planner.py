"""AgentPlanner: plan de trabajo simple, determinista y auditable.

El plan describe QUÉ va a hacer el agente (objetivo, pasos, herramientas,
evidencias esperadas y formato de salida). No contiene razonamiento del
modelo: se construye a partir de la declaración del agente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.security.sanitization import truncate


@dataclass(frozen=True)
class AgentPlan:
    """Plan resumido de trabajo de un agente para una tarea."""

    objective: str
    steps: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    expected_evidence: list[str] = field(default_factory=list)
    output_format: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "steps": self.steps,
            "tools": self.tools,
            "expected_evidence": self.expected_evidence,
            "output_format": self.output_format,
        }


class AgentPlanner:
    """Construye el plan auditable previo a la ejecución del agente."""

    def build(self, agent: BaseAgent, ctx: AgentContext) -> AgentPlan:
        planned_invocations = agent.plan_tools(ctx)
        planned_tools = [plan.tool_name for plan in planned_invocations]

        steps: list[str] = ["Revisar la tarea y el contexto aportado."]
        for invocation in planned_invocations:
            steps.append(f"Ejecutar herramienta '{invocation.tool_name}': {invocation.reason}")
        if ctx.documents_used:
            steps.append(
                f"Incorporar {ctx.documents_used} fragmento(s) de documentos locales como contexto citable."
            )
        steps.append(f"Consultar el modelo '{ctx.model_name}' con prompt estructurado y evidencia.")
        steps.append("Validar la respuesta (verificador) y calcular confianza.")

        expected_evidence: list[str] = [f"Salida JSON de '{name}'" for name in planned_tools]
        if ctx.documents_used:
            expected_evidence.append("Citas de documentos locales (archivo + chunk)")
        if not expected_evidence:
            expected_evidence.append("Solo el texto aportado por el usuario (sin evidencia adicional)")

        return AgentPlan(
            objective=truncate(
                f"Resolver con el agente '{agent.display_name}': {ctx.task}", 300
            ),
            steps=steps,
            tools=planned_tools,
            expected_evidence=expected_evidence,
            output_format=list(agent.output_format),
        )
