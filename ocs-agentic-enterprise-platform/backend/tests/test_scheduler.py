"""Tests del programador de tareas: cálculo de fechas y ejecución de tareas vencidas."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.scheduler.schedule import (
    ScheduleError,
    ScheduleSpec,
    first_run_at,
    next_run_at_after,
    validate_spec,
)
from app.schemas import ScheduledTaskCreate
from app.services import scheduler_service
from app.services.agent_runner import build_default_squad_registry

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Cálculo de próximas ejecuciones (funciones puras)
# ---------------------------------------------------------------------------


def test_once_runs_once_then_stops() -> None:
    run_at = datetime(2026, 6, 20, 8, 0, tzinfo=UTC)
    spec = ScheduleSpec(kind="once", run_at=run_at)
    now = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)
    assert first_run_at(spec, now) == run_at
    assert next_run_at_after(spec, run_at) is None


def test_once_in_the_past_runs_immediately() -> None:
    run_at = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    spec = ScheduleSpec(kind="once", run_at=run_at)
    now = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)
    assert first_run_at(spec, now) == now


def test_interval_advances_by_minutes() -> None:
    spec = ScheduleSpec(kind="interval", interval_minutes=90)
    after = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)
    assert next_run_at_after(spec, after) == after + timedelta(minutes=90)


def test_daily_picks_next_occurrence() -> None:
    spec = ScheduleSpec(kind="daily", time_of_day="09:00", timezone="UTC")
    # 10:00 ya pasó la hora -> al día siguiente
    after = datetime(2026, 6, 14, 10, 0, tzinfo=UTC)
    nxt = next_run_at_after(spec, after)
    assert nxt == datetime(2026, 6, 15, 9, 0, tzinfo=UTC)
    # 08:00 aún no -> hoy mismo
    after2 = datetime(2026, 6, 14, 8, 0, tzinfo=UTC)
    assert next_run_at_after(spec, after2) == datetime(2026, 6, 14, 9, 0, tzinfo=UTC)


def test_daily_respects_timezone() -> None:
    spec = ScheduleSpec(kind="daily", time_of_day="09:00", timezone="Europe/Madrid")
    after = datetime(2026, 6, 14, 6, 0, tzinfo=UTC)  # 08:00 en Madrid (verano, UTC+2)
    nxt = next_run_at_after(spec, after)
    # 09:00 Madrid == 07:00 UTC en horario de verano
    assert nxt == datetime(2026, 6, 14, 7, 0, tzinfo=UTC)


def test_weekly_picks_target_weekday() -> None:
    spec = ScheduleSpec(kind="weekly", time_of_day="09:00", day_of_week=0, timezone="UTC")  # lunes
    after = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)  # domingo
    nxt = next_run_at_after(spec, after)
    assert nxt.weekday() == 0  # lunes
    assert (nxt.hour, nxt.minute) == (9, 0)
    assert nxt > after


def test_cron_every_15_minutes() -> None:
    spec = ScheduleSpec(kind="cron", cron="*/15 * * * *", timezone="UTC")
    after = datetime(2026, 6, 14, 10, 7, tzinfo=UTC)
    assert next_run_at_after(spec, after) == datetime(2026, 6, 14, 10, 15, tzinfo=UTC)


def test_cron_monday_9am() -> None:
    spec = ScheduleSpec(kind="cron", cron="0 9 * * 1", timezone="UTC")  # lunes 09:00
    after = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)  # domingo
    nxt = next_run_at_after(spec, after)
    assert nxt.weekday() == 0 and (nxt.hour, nxt.minute) == (9, 0)


def test_validate_spec_rejects_bad_inputs() -> None:
    with pytest.raises(ScheduleError):
        validate_spec(ScheduleSpec(kind="interval", interval_minutes=0))
    with pytest.raises(ScheduleError):
        validate_spec(ScheduleSpec(kind="daily", time_of_day="25:00"))
    with pytest.raises(ScheduleError):
        validate_spec(ScheduleSpec(kind="weekly", time_of_day="09:00", day_of_week=9))
    with pytest.raises(ScheduleError):
        validate_spec(ScheduleSpec(kind="cron", cron="bad expression"))
    with pytest.raises(ScheduleError):
        validate_spec(ScheduleSpec(kind="daily", time_of_day="09:00", timezone="Mars/Phobos"))


# ---------------------------------------------------------------------------
# Servicio: creación y ejecución de tareas vencidas
# ---------------------------------------------------------------------------


@pytest.fixture()
def squad_names() -> set[str]:
    return set(build_default_squad_registry().names())


def _create(db, agent_registry, squad_names, **overrides):
    payload = {
        "name": "Tarea",
        "task": "Resume el estado del proyecto.",
        "target_kind": "auto",
        "schedule_kind": "interval",
        "interval_minutes": 60,
    }
    payload.update(overrides)
    return scheduler_service.create_task(
        db, ScheduledTaskCreate(**payload), agent_registry=agent_registry, squad_names=squad_names
    )


def test_create_schedules_next_run(db_session, agent_registry, squad_names) -> None:
    task = _create(db_session, agent_registry, squad_names)
    assert task.id is not None
    assert task.enabled is True
    assert task.status == "scheduled"
    assert task.next_run_at is not None
    out = scheduler_service.task_to_out(task)
    assert out.schedule_human.startswith("Cada 60")


def test_create_rejects_unknown_agent(db_session, agent_registry, squad_names) -> None:
    with pytest.raises(ValueError, match="Agente desconocido"):
        _create(db_session, agent_registry, squad_names, target_kind="agent", target_ref="no_existe")


def test_run_due_executes_and_reschedules(
    db_session, fake_llm, tool_registry, agent_registry, squad_names, memory_session_factory
) -> None:
    task = _create(
        db_session, agent_registry, squad_names,
        target_kind="agent", target_ref="business_assistant", model="fake-model",
    )
    assert task.next_run_at is not None
    before = task.next_run_at

    runs = scheduler_service.run_due(
        db_session, llm=fake_llm, tool_registry=tool_registry,
        agent_registry=agent_registry, session_factory=memory_session_factory,
    )
    assert len(runs) == 1
    assert runs[0].status == "completed"
    assert runs[0].execution_id is not None

    db_session.refresh(task)
    assert task.run_count == 1
    assert task.last_status == "completed"
    assert task.next_run_at is not None and task.next_run_at > before  # reprogramada

    # Ya no está vencida: un segundo barrido no la vuelve a ejecutar.
    assert scheduler_service.run_due(
        db_session, llm=fake_llm, tool_registry=tool_registry,
        agent_registry=agent_registry, session_factory=memory_session_factory,
    ) == []


def test_once_task_finishes_after_running(
    db_session, fake_llm, tool_registry, agent_registry, squad_names, memory_session_factory
) -> None:
    past = datetime.now(UTC) - timedelta(hours=1)
    task = _create(
        db_session, agent_registry, squad_names,
        schedule_kind="once", run_at=past, interval_minutes=None, model="fake-model",
    )
    runs = scheduler_service.run_due(
        db_session, llm=fake_llm, tool_registry=tool_registry,
        agent_registry=agent_registry, session_factory=memory_session_factory,
    )
    assert len(runs) == 1
    db_session.refresh(task)
    assert task.enabled is False
    assert task.status == "finished"
    assert task.next_run_at is None


def test_run_due_executes_team(
    db_session, fake_llm, tool_registry, agent_registry, squad_names, memory_session_factory
) -> None:
    task = _create(
        db_session, agent_registry, squad_names,
        target_kind="team", agent_names=["backend_developer", "code_reviewer"],
        schedule_kind="once", run_at=datetime.now(UTC) - timedelta(minutes=1),
        interval_minutes=None, model="fake-model",
    )
    runs = scheduler_service.run_due(
        db_session, llm=fake_llm, tool_registry=tool_registry,
        agent_registry=agent_registry, session_factory=memory_session_factory,
    )
    assert len(runs) == 1 and runs[0].status == "completed"
    from app.models import AgentExecution

    execution = db_session.get(AgentExecution, runs[0].execution_id)
    assert execution is not None and execution.agent_name == "squad:custom"
