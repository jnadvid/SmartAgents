"""Tests del TaskRouter: selección de agente por intención y modo manual."""
from __future__ import annotations

import pytest

from app.orchestration.task_router import INTENT_AGENT_MAP, TaskRouter
from app.orchestration.intent_classifier import INTENT_CATEGORIES


@pytest.fixture()
def router(agent_registry) -> TaskRouter:
    return TaskRouter(agent_registry)


def test_every_intent_has_registered_agent(agent_registry) -> None:
    for intent in INTENT_CATEGORIES:
        agent_name = INTENT_AGENT_MAP.get(intent)
        assert agent_name, f"Intención sin mapeo: {intent}"
        assert agent_registry.get(agent_name) is not None, f"Agente no registrado: {agent_name}"


@pytest.mark.parametrize(
    ("task", "expected_agent"),
    [
        ("Analiza esta alerta Wazuh", "cyber_threat_analyst"),
        ("Hazme una propuesta comercial", "sales_proposal"),
        ("Resume este contrato", "legal_document"),
        ("Analiza este CSV", "data_analyst"),
        ("Hazme un plan de proyecto", "project_manager"),
        ("Prepara formación para empleados", "hr_training"),
        ("Responde a este cliente con una reclamación", "customer_support"),
        ("Genera un informe ejecutivo", "report"),
        ("Evalúa cumplimiento ISO 27001", "compliance"),
    ],
)
def test_routing_examples(router: TaskRouter, task: str, expected_agent: str) -> None:
    decision = router.route(task)
    assert decision.selected_agent == expected_agent
    assert decision.selected_by_router is True
    assert decision.reason


def test_manual_selection_overrides_router(router: TaskRouter) -> None:
    decision = router.route("Analiza esta alerta Wazuh", forced_agent="report")
    assert decision.selected_agent == "report"
    assert decision.selected_by_router is False
    # La intención se sigue registrando como metadato.
    assert decision.detected_intent == "cybersecurity_analysis"


def test_manual_selection_unknown_agent_raises(router: TaskRouter) -> None:
    with pytest.raises(ValueError, match="Agente desconocido"):
        router.route("cualquier tarea", forced_agent="no_existe")


def test_auxiliary_agents_proposed(router: TaskRouter) -> None:
    decision = router.route("Analiza esta alerta Wazuh de ransomware")
    assert "report" in decision.auxiliary_agents
