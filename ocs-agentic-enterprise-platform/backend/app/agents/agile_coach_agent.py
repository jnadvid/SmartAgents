"""Agente agile coach (Scrum/Kanban)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class AgileCoachAgent(BaseAgent):
    name = "agile_coach"
    display_name = "Agile Coach"
    category = "projects"
    description = (
        "Facilita la agilidad: Scrum/Kanban, ceremonias, métricas de flujo, "
        "refinamiento del backlog y mejora continua del equipo."
    )
    system_prompt = """
Eres un Agile Coach experimentado (Scrum y Kanban).

Método de trabajo:
- Adapta el marco al contexto del equipo; evita el dogmatismo y el 'agile de cartón'.
- Diseña ceremonias con objetivo claro, time-box y resultado esperado.
- Propón métricas de flujo útiles (lead/cycle time, throughput, WIP) y cómo leerlas.
- Ayuda a escribir historias y criterios de aceptación verificables (INVEST).
- Enfócate en impedimentos reales y en la mejora continua del equipo.
""".strip()
    allowed_tools = ["create_project_plan", "extract_action_items", "extract_risks"]
    output_format = [
        "Resumen",
        "Diagnóstico de agilidad",
        "Marco y ceremonias",
        "Backlog e historias (INVEST)",
        "Métricas de flujo",
        "Plan de mejora",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        return [
            ToolInvocationPlan(
                tool_name="extract_action_items",
                tool_input={"text": f"{ctx.task}\n{ctx.extra_context or ''}"[:100000]},
                reason="Detectar impedimentos y acciones de mejora mencionados.",
            )
        ]
