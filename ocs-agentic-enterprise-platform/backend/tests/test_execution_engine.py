"""Tests del motor de ejecución: ejecuciones, Chain-of-Work y selección automática."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import AgentExecution, ChainOfWorkStep, TaskRoute, ToolLog
from app.orchestration.execution_engine import ExecutionEngine
from app.security.policies import PolicyViolation


@pytest.fixture()
def engine(db_session, fake_llm, tool_registry, agent_registry, memory_session_factory) -> ExecutionEngine:
    return ExecutionEngine(
        db=db_session,
        llm=fake_llm,
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        session_factory=memory_session_factory,
    )


def test_auto_execution_creates_execution_and_chain_of_work(engine, db_session) -> None:
    result = engine.run(
        task="Hazme una propuesta comercial para una empresa de logística que necesita auditoría de seguridad",
        model="fake-model",
    )

    execution = result.execution
    assert execution.id is not None
    assert execution.status == "completed"
    assert execution.agent_name == "sales_proposal"  # selección automática
    assert execution.selected_by_router is True
    assert execution.intent == "sales_proposal"
    assert execution.model_name == "fake-model"
    assert execution.final_output
    assert execution.finished_at is not None
    assert 0.0 <= (execution.confidence_score or 0) <= 1.0

    # Chain-of-Work completo y ordenado
    step_types = [step.step_type for step in result.steps]
    for expected in (
        "task_received",
        "intent_classification",
        "agent_selection",
        "work_plan",
        "tool_call",
        "llm_call",
        "response_verification",
        "confidence_scoring",
        "final_result",
    ):
        assert expected in step_types, f"Falta paso {expected}: {step_types}"
    numbers = [step.step_number for step in result.steps]
    assert numbers == sorted(numbers) and numbers[0] == 1

    # Persistencia en SQLite
    stored_steps = list(
        db_session.execute(
            select(ChainOfWorkStep).where(ChainOfWorkStep.execution_id == execution.id)
        ).scalars()
    )
    assert len(stored_steps) == len(result.steps)
    route = db_session.execute(
        select(TaskRoute).where(TaskRoute.execution_id == execution.id)
    ).scalar_one()
    assert route.selected_agent == "sales_proposal"
    tool_logs = list(
        db_session.execute(select(ToolLog).where(ToolLog.execution_id == execution.id)).scalars()
    )
    assert tool_logs and tool_logs[0].tool_name == "create_sales_proposal"

    # Verificación y confianza
    assert result.verification is not None and result.verification.passed
    assert result.confidence is not None and 0.05 <= result.confidence.score <= 0.95


def test_manual_agent_selection(engine) -> None:
    result = engine.run(task="Genera unas notas sobre la reunión de mañana", agent_name="report", model="fake-model")
    assert result.execution.agent_name == "report"
    assert result.execution.selected_by_router is False


def test_cyber_agent_runs_specialized_tools(engine, fake_llm) -> None:
    result = engine.run(
        task="Analiza esta alerta Wazuh de fuerza bruta contra SSH",
        model="fake-model",
    )
    assert result.execution.agent_name == "cyber_threat_analyst"
    tool_names = {tr.tool_name for tr in result.tool_results}
    assert "map_to_mitre_attack" in tool_names
    # El prompt enviado al modelo incluye la evidencia de herramientas
    last_chat = fake_llm.chat_calls[-1]
    user_message = next(m["content"] for m in last_chat if m["role"] == "user")
    assert "EVIDENCIA DE HERRAMIENTAS" in user_message


def test_llm_down_marks_execution_failed(db_session, down_llm, tool_registry, agent_registry, memory_session_factory) -> None:
    engine = ExecutionEngine(
        db=db_session,
        llm=down_llm,
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        session_factory=memory_session_factory,
    )
    result = engine.run(task="Analiza este CSV de ventas", model="fake-model")
    execution = result.execution
    assert execution.status == "failed"
    assert "conectar" in (execution.error_message or "").lower()
    step_types = [step.step_type for step in result.steps]
    assert "error" in step_types
    # La ejecución fallida también queda persistida y auditada.
    stored = db_session.get(AgentExecution, execution.id)
    assert stored is not None and stored.status == "failed"


def test_unknown_model_fails_with_clear_message(engine) -> None:
    result = engine.run(task="Hazme un plan de proyecto de 4 semanas", model="modelo-inexistente")
    assert result.execution.status == "failed"
    assert "ollama pull" in (result.execution.error_message or "").lower()


def test_empty_task_rejected(engine) -> None:
    with pytest.raises(ValueError):
        engine.run(task="   ")


def test_oversized_task_rejected(engine) -> None:
    with pytest.raises(PolicyViolation):
        engine.run(task="x" * 100000)


def test_unknown_manual_agent_rejected(engine) -> None:
    with pytest.raises(ValueError, match="Agente desconocido"):
        engine.run(task="hola", agent_name="agente_fantasma")


def test_delete_execution_cascades(engine, db_session) -> None:
    from app.services import execution_service

    result = engine.run(task="Hazme un plan de proyecto de 4 semanas", model="fake-model")
    eid = result.execution.id
    assert execution_service.delete_execution(db_session, eid) is True
    assert db_session.get(AgentExecution, eid) is None
    remaining = db_session.execute(
        select(ChainOfWorkStep).where(ChainOfWorkStep.execution_id == eid)
    ).scalars().all()
    assert remaining == []  # los pasos se borran en cascada
    assert execution_service.delete_execution(db_session, eid) is False


def test_delete_executions_by_status(engine, db_session) -> None:
    from app.services import execution_service

    engine.run(task="Hazme un plan de proyecto de 4 semanas", model="fake-model")
    engine.run(task="Analiza este CSV de ventas", model="modelo-inexistente")  # falla
    deleted = execution_service.delete_executions(db_session, status="failed")
    assert deleted >= 1
    assert all(e.status != "failed" for e in execution_service.list_executions(db_session))


def test_secrets_are_redacted_in_audit_trail(engine, db_session) -> None:
    result = engine.run(
        task="Organiza mi semana. Mi api_key=sk-abcdefghijklmnop1234 no debería guardarse.",
        model="fake-model",
    )
    execution = result.execution
    assert "sk-abcdefghijklmnop1234" not in (execution.user_input or "")
    for step in result.steps:
        for field in (step.description, step.evidence, step.tool_input_summary):
            assert not (field and "sk-abcdefghijklmnop1234" in field)
