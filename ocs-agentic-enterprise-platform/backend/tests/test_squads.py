"""Tests de ejecución multi-agente (squads)."""
from __future__ import annotations

import pytest

from app.agents.squads import build_default_squad_registry
from app.orchestration.execution_engine import ExecutionEngine
from app.services.agent_runner import AgentRunner

_PY_CODE = """\
```python
def suma(a, b):
    password = "hardcoded-secret-123"
    return eval(f"{a}+{b}")
```
"""


@pytest.fixture()
def engine(db_session, fake_llm, tool_registry, agent_registry, memory_session_factory) -> ExecutionEngine:
    return ExecutionEngine(
        db=db_session,
        llm=fake_llm,
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        session_factory=memory_session_factory,
    )


def test_default_squads_reference_registered_agents(agent_registry) -> None:
    squads = build_default_squad_registry()
    missing = squads.validate_against(agent_registry)
    assert missing == [], f"Squads con agentes inexistentes: {missing}"
    assert len(squads.names()) >= 6


def test_run_squad_pipeline_runs_all_members(engine, db_session) -> None:
    result = engine.run_squad(
        task="Diseña y revisa una función de suma en Python.",
        members=["software_architect", "code_reviewer", "qa_test_engineer"],
        squad_label="squad:custom",
        squad_display="Equipo personalizado",
        model="fake-model",
        extra_context=_PY_CODE,
    )
    execution = result.execution
    assert execution.status == "completed"
    assert execution.agent_name == "squad:custom"
    assert execution.intent == "multi_agent"

    # La salida combina el trabajo de los tres agentes.
    assert "Arquitecto de Software" in execution.final_output
    assert "Revisor de Código" in execution.final_output
    assert "Ingeniero de QA" in execution.final_output

    # El Chain-of-Work registra la selección del equipo y un paso por agente.
    step_types = [s.step_type for s in result.steps]
    assert step_types.count("agent_run") == 3
    assert "squad_selection" in step_types
    assert "final_result" in step_types

    # Hubo evidencia de herramientas de código.
    tool_names = {tr.tool_name for tr in result.tool_results}
    assert tool_names & {"review_code_quality", "analyze_code_structure", "generate_test_skeleton"}


def test_run_squad_unknown_member_raises(engine) -> None:
    with pytest.raises(ValueError, match="desconocido"):
        engine.run_squad(
            task="hola",
            members=["backend_developer", "agente_fantasma"],
            squad_label="squad:custom",
            squad_display="Equipo personalizado",
        )


def test_agent_runner_executes_predefined_squad(db_session, fake_llm, tool_registry, agent_registry, memory_session_factory) -> None:
    runner = AgentRunner(
        db_session,
        llm=fake_llm,
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        session_factory=memory_session_factory,
    )
    squads = runner.list_squads()
    assert any(s.name == "dev_team" for s in squads)

    from app.schemas import SquadExecuteRequest

    response = runner.execute_squad(
        SquadExecuteRequest(task="Implementa y prueba un endpoint de login.", squad_name="dev_team", model="fake-model")
    )
    assert response.status == "completed"
    assert response.agent_name == "squad:dev_team"
    assert len(response.auxiliary_agents) == 5  # miembros del equipo


def test_adhoc_squad_requires_two_agents(db_session, fake_llm, tool_registry, agent_registry, memory_session_factory) -> None:
    runner = AgentRunner(
        db_session, llm=fake_llm, tool_registry=tool_registry,
        agent_registry=agent_registry, session_factory=memory_session_factory,
    )
    from app.schemas import SquadExecuteRequest

    with pytest.raises(ValueError, match="al menos 2"):
        runner.execute_squad(SquadExecuteRequest(task="x", agent_names=["backend_developer"]))
