"""Tests de los agentes especializados de seguridad (blue/red/purple, SOC, OT)."""
from __future__ import annotations

import pytest

from app.orchestration.task_router import TaskRouter

_NEW_AGENTS = [
    "soc_manager", "blue_team_analyst", "threat_hunter", "detection_engineer",
    "red_team_operator", "purple_team_lead", "ot_security_analyst", "cyberpsychology_analyst",
]


def test_new_security_agents_registered(agent_registry) -> None:
    for name in _NEW_AGENTS:
        assert agent_registry.get(name) is not None, f"Falta el agente {name}"


def test_soc_manager_has_routing_and_conclusion_sections(agent_registry) -> None:
    soc = agent_registry.get("soc_manager")
    assert "Decisión de derivación" in soc.output_format
    assert "Conclusión final" in soc.output_format
    # El jefe de SOC puede leer alertas de Wazuh.
    assert "wazuh_alerts" in soc.data_access


def test_red_team_uses_security_testing_policy(agent_registry) -> None:
    red = agent_registry.get("red_team_operator")
    assert red.security_policy == "security_testing"
    # No lee fuentes de producción en vivo.
    assert red.data_access == []


@pytest.mark.parametrize(
    ("task", "expected_agent"),
    [
        ("Investiga la alerta como blue team", "blue_team_analyst"),
        ("Ejercicio de red team autorizado de emulación de adversario", "red_team_operator"),
        ("Purple team: construye la matriz de cobertura", "purple_team_lead"),
        ("Evalúa la ciberseguridad industrial del entorno SCADA", "ot_security_analyst"),
        ("Crea una regla sigma de detección", "detection_engineer"),
        ("Caza de amenazas con hipótesis sobre persistencia", "threat_hunter"),
        ("Analiza la psicología de la ciberseguridad y la ingeniería social", "cyberpsychology_analyst"),
    ],
)
def test_security_routing(agent_registry, task: str, expected_agent: str) -> None:
    decision = TaskRouter(agent_registry).route(task)
    assert decision.selected_agent == expected_agent


def test_soc_squad_exists_with_chief_last(agent_registry) -> None:
    from app.agents.squads import build_default_squad_registry

    squad = build_default_squad_registry().get("soc_investigation_team")
    assert squad is not None
    assert squad.members[-1] == "soc_manager"  # el jefe decide al final
    assert build_default_squad_registry().validate_against(agent_registry) == []
