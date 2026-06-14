"""Squads: equipos de agentes que colaboran en una misma tarea.

Un squad ejecuta a sus miembros en cadena (modo 'pipeline'): cada agente
recibe la tarea original más el resultado acumulado de los agentes previos,
de modo que el trabajo se va refinando (p. ej. arquitecto -> backend ->
revisor -> QA). Todo queda en una única ejecución auditable (Chain-of-Work).

Además de los squads predefinidos, el usuario puede componer un equipo
ad-hoc indicando una lista de agentes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from app.agents.registry import AgentRegistry


@dataclass(frozen=True)
class Squad:
    """Equipo nombrado de agentes que colaboran en cadena."""

    name: str
    display_name: str
    category: str
    description: str
    members: list[str] = field(default_factory=list)
    mode: str = "pipeline"  # por ahora solo 'pipeline'

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "category": self.category,
            "description": self.description,
            "members": list(self.members),
            "mode": self.mode,
        }


class SquadRegistry:
    """Catálogo en memoria de squads predefinidos."""

    def __init__(self) -> None:
        self._squads: dict[str, Squad] = {}

    def register(self, squad: Squad) -> None:
        if squad.name in self._squads:
            raise ValueError(f"Squad duplicado en el registro: '{squad.name}'")
        self._squads[squad.name] = squad

    def register_all(self, squads: Iterable[Squad]) -> None:
        for squad in squads:
            self.register(squad)

    def get(self, name: str) -> Squad | None:
        return self._squads.get(name)

    def names(self) -> list[str]:
        return sorted(self._squads)

    def list_squads(self) -> list[Squad]:
        return [self._squads[name] for name in self.names()]

    def validate_against(self, agent_registry: AgentRegistry) -> list[str]:
        """Devuelve la lista de miembros referenciados que no existen (debe ser vacía)."""
        missing: list[str] = []
        for squad in self.list_squads():
            for member in squad.members:
                if agent_registry.get(member) is None:
                    missing.append(f"{squad.name}:{member}")
        return missing


# Squads predefinidos. Todos los miembros deben existir en el registro de agentes.
DEFAULT_SQUADS: tuple[Squad, ...] = (
    Squad(
        name="dev_team",
        display_name="Equipo de Desarrollo",
        category="programming",
        description=(
            "Ciclo completo de desarrollo: arquitectura, implementación backend y "
            "frontend, revisión de código y pruebas."
        ),
        members=[
            "software_architect",
            "backend_developer",
            "frontend_developer",
            "code_reviewer",
            "qa_test_engineer",
        ],
    ),
    Squad(
        name="secure_dev_team",
        display_name="Desarrollo Seguro (DevSecOps)",
        category="programming",
        description=(
            "Desarrollo con seguridad integrada: arquitectura, backend, revisión "
            "AppSec (SAST/CWE), revisión de código y pruebas."
        ),
        members=[
            "software_architect",
            "backend_developer",
            "appsec_engineer",
            "code_reviewer",
            "qa_test_engineer",
        ],
    ),
    Squad(
        name="code_review_squad",
        display_name="Revisión de Código 360º",
        category="programming",
        description="Revisión de calidad, seguridad (AppSec) y testabilidad de un código existente.",
        members=["code_reviewer", "appsec_engineer", "qa_test_engineer"],
    ),
    Squad(
        name="incident_response_team",
        display_name="Equipo de Respuesta a Incidentes",
        category="cybersecurity",
        description=(
            "Respuesta a incidentes con inteligencia de amenazas, implicaciones de "
            "cumplimiento e informe ejecutivo."
        ),
        members=["incident_responder", "threat_intel_analyst", "compliance", "report"],
    ),
    Squad(
        name="product_launch_team",
        display_name="Lanzamiento de Producto",
        category="business",
        description=(
            "De la investigación de mercado a la estrategia, la propuesta comercial y "
            "el plan de proyecto del lanzamiento."
        ),
        members=["market_research", "strategy_consultant", "sales_proposal", "project_manager"],
    ),
    Squad(
        name="compliance_audit_team",
        display_name="Auditoría de Cumplimiento",
        category="compliance",
        description=(
            "Gap analysis de cumplimiento, protección de datos (DPO), auditoría "
            "documental e informe."
        ),
        members=["compliance", "data_protection_officer", "document_audit", "report"],
    ),
    Squad(
        name="people_team",
        display_name="Equipo de Personas",
        category="hr",
        description="Selección, gestión de personas y psicología organizacional para retos de RRHH.",
        members=["recruiter", "people_ops", "organizational_psychologist"],
    ),
    Squad(
        name="data_initiative_team",
        display_name="Iniciativa de Datos",
        category="data",
        description="Análisis de datos, lectura estratégica e informe ejecutivo.",
        members=["data_analyst", "strategy_consultant", "report"],
    ),
)


def build_default_squad_registry() -> SquadRegistry:
    """Construye el registro con los squads predefinidos."""
    registry = SquadRegistry()
    registry.register_all(DEFAULT_SQUADS)
    return registry
