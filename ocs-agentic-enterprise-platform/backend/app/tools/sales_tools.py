"""Herramientas de ventas: esqueleto estructurado de propuesta comercial."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolContext


class CreateSalesProposalInput(BaseModel):
    client: str | None = Field(default=None, max_length=200, description="Cliente u organización")
    need: str = Field(min_length=3, max_length=20000, description="Necesidad detectada o brief")
    solution: str | None = Field(default=None, max_length=20000, description="Solución prevista")
    budget_range: str | None = Field(default=None, max_length=100)
    timeline: str | None = Field(default=None, max_length=200)


class CreateSalesProposalTool(BaseTool):
    name = "create_sales_proposal"
    category = "sales"
    description = (
        "Genera el esqueleto estructurado de una propuesta comercial (secciones, "
        "campos a completar y checklist) a partir de la necesidad del cliente."
    )
    input_schema = CreateSalesProposalInput
    timeout_seconds = 10

    def execute(self, payload: CreateSalesProposalInput, ctx: ToolContext) -> dict[str, Any]:
        client = payload.client or "[Cliente por confirmar]"
        sections = [
            {"title": "Resumen ejecutivo", "guidance": "2-3 párrafos: problema, solución y valor."},
            {"title": "Necesidad detectada", "guidance": payload.need[:500]},
            {"title": "Solución propuesta", "guidance": (payload.solution or "[Describir solución]")[:500]},
            {"title": "Alcance", "guidance": "Qué incluye y qué queda explícitamente fuera."},
            {"title": "Entregables", "guidance": "Lista verificable de entregables con criterios de aceptación."},
            {"title": "Plan y plazos", "guidance": payload.timeline or "[Definir hitos y fechas]"},
            {"title": "Inversión", "guidance": payload.budget_range or "[Definir rango de inversión]"},
            {"title": "Diferenciadores", "guidance": "Por qué nosotros: experiencia, método, garantías."},
            {"title": "Próximos pasos", "guidance": "Acción concreta con fecha (reunión, piloto, firma)."},
        ]
        missing = [
            field_name
            for field_name, value in (
                ("client", payload.client),
                ("solution", payload.solution),
                ("budget_range", payload.budget_range),
                ("timeline", payload.timeline),
            )
            if not value
        ]
        return {
            "client": client,
            "sections": sections,
            "missing_fields": missing,
            "checklist": [
                "Validar necesidad con el contacto del cliente",
                "Confirmar presupuesto y plazos",
                "Revisar alcance con el equipo de entrega",
                "Definir criterios de aceptación medibles",
            ],
        }
