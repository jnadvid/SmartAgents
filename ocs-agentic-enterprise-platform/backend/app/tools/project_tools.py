"""Herramientas de gestión de proyectos: esqueleto de plan auditable."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolContext


class CreateProjectPlanInput(BaseModel):
    objective: str = Field(min_length=3, max_length=20000)
    duration_weeks: int = Field(default=8, ge=1, le=104)
    team_size: int | None = Field(default=None, ge=1, le=200)


class CreateProjectPlanTool(BaseTool):
    name = "create_project_plan"
    category = "projects"
    description = (
        "Genera un esqueleto de plan de proyecto (fases, hitos, riesgos genéricos "
        "y reparto temporal) a partir del objetivo y la duración."
    )
    input_schema = CreateProjectPlanInput
    timeout_seconds = 10

    def execute(self, payload: CreateProjectPlanInput, ctx: ToolContext) -> dict[str, Any]:
        duration = payload.duration_weeks
        # Reparto temporal estándar: 15% inicio, 20% planificación,
        # 50% ejecución, 15% cierre (mínimo 1 semana por fase).
        weights = [("Inicio", 0.15), ("Planificación", 0.20), ("Ejecución", 0.50), ("Cierre", 0.15)]
        phases: list[dict[str, Any]] = []
        week_cursor = 1
        for index, (phase_name, weight) in enumerate(weights):
            weeks = max(1, round(duration * weight))
            if index == len(weights) - 1:
                weeks = max(1, duration - week_cursor + 1)
            phase_tasks = {
                "Inicio": [
                    "Definir alcance y criterios de éxito",
                    "Identificar interesados y responsable de cada área",
                    "Aprobar presupuesto y recursos",
                ],
                "Planificación": [
                    "Desglosar entregables en tareas",
                    "Estimar esfuerzo y asignar responsables",
                    "Definir plan de riesgos y comunicación",
                ],
                "Ejecución": [
                    "Ejecutar tareas por iteraciones cortas",
                    "Seguimiento semanal de avance y bloqueos",
                    "Gestionar cambios de alcance de forma controlada",
                ],
                "Cierre": [
                    "Validar entregables contra criterios de aceptación",
                    "Documentar lecciones aprendidas",
                    "Traspaso a operación / soporte",
                ],
            }[phase_name]
            phases.append(
                {
                    "phase": phase_name,
                    "start_week": week_cursor,
                    "end_week": min(duration, week_cursor + weeks - 1),
                    "tasks": phase_tasks,
                }
            )
            week_cursor += weeks

        milestones = [
            {"week": phases[0]["end_week"], "milestone": "Kick-off completado y alcance aprobado"},
            {"week": phases[1]["end_week"], "milestone": "Plan detallado y riesgos aprobados"},
            {"week": max(1, round(duration * 0.6)), "milestone": "Revisión intermedia de avance"},
            {"week": duration, "milestone": "Entrega final y cierre"},
        ]

        return {
            "objective": payload.objective[:500],
            "duration_weeks": duration,
            "team_size": payload.team_size,
            "phases": phases,
            "milestones": milestones,
            "generic_risks": [
                "Alcance mal definido o cambiante (scope creep)",
                "Dependencias externas sin fecha comprometida",
                "Disponibilidad parcial del equipo clave",
                "Retrasos en aprobaciones o decisiones",
            ],
            "note": "Esqueleto orientativo: el agente debe adaptarlo al contexto real de la tarea.",
        }
