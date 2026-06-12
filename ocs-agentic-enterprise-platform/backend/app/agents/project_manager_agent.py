"""Agente de gestión de proyectos."""
from __future__ import annotations

import re

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan

_DURATION_PATTERN = re.compile(r"(\d{1,3})\s*(semana|semanas|week|weeks)", re.IGNORECASE)
_DURATION_MONTHS = re.compile(r"(\d{1,2})\s*(mes|meses|month|months)", re.IGNORECASE)


class ProjectManagerAgent(BaseAgent):
    name = "project_manager"
    display_name = "Gestor de Proyectos"
    category = "projects"
    description = (
        "Crea planes de proyecto: fases, tareas, cronograma, responsables, "
        "hitos, riesgos y dependencias."
    )
    system_prompt = """
Eres un director de proyectos senior (metodologías predictivas y ágiles).

Método de trabajo:
- Usa el esqueleto de la herramienta `create_project_plan` como base
  temporal y adáptalo al contexto real de la tarea.
- Las tareas deben ser concretas y agrupadas por fase; los hitos,
  verificables (entregable + criterio).
- Los responsables son SUGERIDOS por rol (no inventes nombres de personas).
- Señala dependencias entre tareas y supuestos de planificación.
""".strip()
    allowed_tools = ["create_project_plan", "extract_action_items", "extract_risks"]
    output_format = [
        "Objetivo",
        "Fases",
        "Tareas",
        "Responsables sugeridos",
        "Hitos",
        "Riesgos",
        "Dependencias",
        "Próximos pasos",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        text = f"{ctx.task}\n{ctx.extra_context or ''}"
        duration_weeks = 8
        weeks_match = _DURATION_PATTERN.search(text)
        months_match = _DURATION_MONTHS.search(text)
        if weeks_match:
            duration_weeks = max(1, min(104, int(weeks_match.group(1))))
        elif months_match:
            duration_weeks = max(1, min(104, int(months_match.group(1)) * 4))

        return [
            ToolInvocationPlan(
                tool_name="create_project_plan",
                tool_input={"objective": ctx.task[:20000], "duration_weeks": duration_weeks},
                reason=f"Generar esqueleto temporal de plan para {duration_weeks} semanas.",
            )
        ]
