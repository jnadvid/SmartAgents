"""Servicio del programador de tareas: CRUD y ejecución de tareas vencidas.

La fuente de verdad es SQLite: cada tarea guarda su próxima ejecución
(`next_run_at`). El hilo del scheduler (o un disparo manual) pide las tareas
vencidas, las ejecuta a través del `AgentRunner` y reprograma la siguiente.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.registry import AgentRegistry
from app.llm.base import BaseLLMProvider
from app.models import ScheduledRun, ScheduledTask
from app.scheduler.schedule import (
    ScheduleError,
    ScheduleSpec,
    describe_schedule,
    first_run_at,
    next_run_at_after,
    validate_spec,
)
from app.schemas import (
    ExecuteRequest,
    ScheduledRunOut,
    ScheduledTaskCreate,
    ScheduledTaskDetail,
    ScheduledTaskOut,
    ScheduledTaskUpdate,
    SquadExecuteRequest,
)
from app.security.policies import PolicyViolation
from app.security.sanitization import summarize_for_log
from app.services.agent_runner import AgentRunner
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_MAX_TASKS_PER_TICK = 25


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Especificación y validación
# ---------------------------------------------------------------------------


def spec_from_task(task: ScheduledTask) -> ScheduleSpec:
    return ScheduleSpec(
        kind=task.schedule_kind,
        run_at=task.run_at,
        interval_minutes=task.interval_minutes,
        time_of_day=task.time_of_day,
        day_of_week=task.day_of_week,
        cron=task.cron,
        timezone=task.timezone or "UTC",
    )


def _validate_target(
    target_kind: str,
    target_ref: str | None,
    agent_names: list[str] | None,
    agent_registry: AgentRegistry,
    squad_names: set[str],
) -> None:
    """Valida que el objetivo (agente/squad/equipo) existe. Lanza ValueError si no."""
    if target_kind == "auto":
        return
    if target_kind == "agent":
        if not target_ref or agent_registry.get(target_ref) is None:
            raise ValueError(f"Agente desconocido para la tarea programada: '{target_ref}'.")
    elif target_kind == "squad":
        if not target_ref or target_ref not in squad_names:
            raise ValueError(f"Equipo (squad) desconocido: '{target_ref}'.")
    elif target_kind == "team":
        members = [n for n in (agent_names or []) if n]
        if len(members) < 2:
            raise ValueError("Un equipo ad-hoc requiere al menos 2 agentes.")
        unknown = [n for n in members if agent_registry.get(n) is None]
        if unknown:
            raise ValueError(f"Agentes desconocidos en el equipo: {', '.join(unknown)}.")
    else:
        raise ValueError(f"Tipo de objetivo no soportado: '{target_kind}'.")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_task(
    db: Session,
    payload: ScheduledTaskCreate,
    *,
    agent_registry: AgentRegistry,
    squad_names: set[str],
) -> ScheduledTask:
    spec = ScheduleSpec(
        kind=payload.schedule_kind,
        run_at=payload.run_at,
        interval_minutes=payload.interval_minutes,
        time_of_day=payload.time_of_day,
        day_of_week=payload.day_of_week,
        cron=payload.cron,
        timezone=payload.timezone or "UTC",
    )
    validate_spec(spec)  # ScheduleError -> ValueError (subclase)
    _validate_target(payload.target_kind, payload.target_ref, payload.agent_names, agent_registry, squad_names)

    now = utcnow()
    next_run = first_run_at(spec, now)
    task = ScheduledTask(
        name=payload.name.strip(),
        task=payload.task,
        extra_context=payload.extra_context,
        model=payload.model,
        use_documents=payload.use_documents,
        target_kind=payload.target_kind,
        target_ref=(payload.target_ref or ""),
        agent_names=json.dumps(payload.agent_names or [], ensure_ascii=False),
        schedule_kind=payload.schedule_kind,
        run_at=spec.run_at,
        interval_minutes=payload.interval_minutes,
        time_of_day=payload.time_of_day,
        day_of_week=payload.day_of_week,
        cron=payload.cron,
        timezone=payload.timezone or "UTC",
        enabled=True,
        status="scheduled",
        next_run_at=next_run,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    logger.info(
        "Tarea programada creada",
        extra={"extra_data": {"task_id": task.id, "kind": task.schedule_kind, "next_run_at": str(next_run)}},
    )
    return task


def list_tasks(db: Session, *, enabled: bool | None = None) -> list[ScheduledTask]:
    stmt = select(ScheduledTask).order_by(ScheduledTask.id.desc())
    if enabled is not None:
        stmt = stmt.where(ScheduledTask.enabled == enabled)
    return list(db.execute(stmt).scalars())


def get_task(db: Session, task_id: int) -> ScheduledTask | None:
    return db.get(ScheduledTask, task_id)


def delete_task(db: Session, task: ScheduledTask) -> None:
    db.delete(task)
    db.commit()


def update_task(
    db: Session,
    task: ScheduledTask,
    payload: ScheduledTaskUpdate,
    *,
    agent_registry: AgentRegistry,
    squad_names: set[str],
) -> ScheduledTask:
    data = payload.model_dump(exclude_unset=True)

    for field in ("name", "task", "extra_context", "model", "use_documents", "target_ref",
                  "schedule_kind", "run_at", "interval_minutes", "time_of_day",
                  "day_of_week", "cron", "timezone", "target_kind"):
        if field in data and data[field] is not None:
            setattr(task, field, data[field])
    if "agent_names" in data and data["agent_names"] is not None:
        task.agent_names = json.dumps(data["agent_names"], ensure_ascii=False)

    # Validar objetivo y programación tras los cambios.
    _validate_target(
        task.target_kind, task.target_ref, json.loads(task.agent_names or "[]"),
        agent_registry, squad_names,
    )
    spec = spec_from_task(task)
    validate_spec(spec)

    # Habilitar/pausar y recalcular próxima ejecución.
    if "enabled" in data and data["enabled"] is not None:
        task.enabled = data["enabled"]

    if not task.enabled:
        task.status = "paused"
        task.next_run_at = None
    else:
        task.status = "scheduled"
        # Recalcular desde ahora (cambios de programación o reactivación).
        task.next_run_at = first_run_at(spec, utcnow())

    db.commit()
    db.refresh(task)
    return task


def set_enabled(db: Session, task: ScheduledTask, enabled: bool) -> ScheduledTask:
    task.enabled = enabled
    if enabled:
        task.status = "scheduled"
        task.next_run_at = first_run_at(spec_from_task(task), utcnow())
    else:
        task.status = "paused"
        task.next_run_at = None
    db.commit()
    db.refresh(task)
    return task


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------


def _dispatch(db: Session, task: ScheduledTask, runner: AgentRunner):
    """Ejecuta la tarea según su objetivo y devuelve la ExecutionResponse."""
    if task.target_kind == "agent":
        return runner.execute(
            ExecuteRequest(
                task=task.task, agent_name=task.target_ref or None, model=task.model,
                use_documents=task.use_documents, extra_context=task.extra_context,
            )
        )
    if task.target_kind == "squad":
        return runner.execute_squad(
            SquadExecuteRequest(
                task=task.task, squad_name=task.target_ref or None, model=task.model,
                use_documents=task.use_documents, extra_context=task.extra_context,
            )
        )
    if task.target_kind == "team":
        return runner.execute_squad(
            SquadExecuteRequest(
                task=task.task, agent_names=json.loads(task.agent_names or "[]"), model=task.model,
                use_documents=task.use_documents, extra_context=task.extra_context,
            )
        )
    # auto
    return runner.execute(
        ExecuteRequest(
            task=task.task, agent_name=None, model=task.model,
            use_documents=task.use_documents, extra_context=task.extra_context,
        )
    )


def execute_one(
    db: Session,
    task: ScheduledTask,
    *,
    llm: BaseLLMProvider,
    tool_registry: ToolRegistry,
    agent_registry: AgentRegistry,
    session_factory,
) -> ScheduledRun:
    """Ejecuta una tarea programada una vez, registra el run y reprograma."""
    started = utcnow()
    runner = AgentRunner(
        db, llm=llm, tool_registry=tool_registry,
        agent_registry=agent_registry, session_factory=session_factory,
    )
    execution_id: int | None = None
    status = "completed"
    message = ""
    try:
        response = _dispatch(db, task, runner)
        execution_id = response.execution_id
        status = response.status
        message = response.error_message or ""
    except (ValueError, PolicyViolation) as exc:
        status = "error"
        message = summarize_for_log(str(exc), 400)
        logger.warning("Tarea programada %s con objetivo inválido: %s", task.id, message)
    except Exception as exc:  # noqa: BLE001 - frontera: nunca tumbar el scheduler
        status = "error"
        message = summarize_for_log(str(exc), 400)
        logger.exception("Error ejecutando la tarea programada %s", task.id)

    finished = utcnow()
    run = ScheduledRun(
        scheduled_task_id=task.id,
        execution_id=execution_id,
        status=status,
        message=message,
        started_at=started,
        finished_at=finished,
    )
    db.add(run)

    # Reprogramar.
    task.last_run_at = finished
    task.last_status = status
    task.last_execution_id = execution_id
    task.run_count = (task.run_count or 0) + 1
    next_run = next_run_at_after(spec_from_task(task), finished)
    if next_run is None:
        task.enabled = False
        task.status = "finished"
        task.next_run_at = None
    else:
        task.next_run_at = next_run
        task.status = "scheduled"

    db.commit()
    db.refresh(run)
    logger.info(
        "Tarea programada ejecutada",
        extra={"extra_data": {"task_id": task.id, "status": status, "next_run_at": str(task.next_run_at)}},
    )
    return run


def due_tasks(db: Session, now: datetime | None = None) -> list[ScheduledTask]:
    now = now or utcnow()
    stmt = (
        select(ScheduledTask)
        .where(ScheduledTask.enabled.is_(True))
        .where(ScheduledTask.next_run_at.is_not(None))
        .where(ScheduledTask.next_run_at <= now)
        .order_by(ScheduledTask.next_run_at)
        .limit(_MAX_TASKS_PER_TICK)
    )
    return list(db.execute(stmt).scalars())


def run_due(
    db: Session,
    *,
    llm: BaseLLMProvider,
    tool_registry: ToolRegistry,
    agent_registry: AgentRegistry,
    session_factory,
    now: datetime | None = None,
) -> list[ScheduledRun]:
    """Ejecuta todas las tareas vencidas. Aísla los fallos por tarea."""
    runs: list[ScheduledRun] = []
    for task in due_tasks(db, now):
        try:
            runs.append(
                execute_one(
                    db, task, llm=llm, tool_registry=tool_registry,
                    agent_registry=agent_registry, session_factory=session_factory,
                )
            )
        except Exception:  # noqa: BLE001 - nunca interrumpir el resto del lote
            logger.exception("Fallo no controlado ejecutando la tarea programada %s", task.id)
            db.rollback()
    return runs


# ---------------------------------------------------------------------------
# Serialización a schemas
# ---------------------------------------------------------------------------


def task_to_out(task: ScheduledTask) -> ScheduledTaskOut:
    try:
        human = describe_schedule(spec_from_task(task))
    except ScheduleError:
        human = task.schedule_kind
    return ScheduledTaskOut(
        id=task.id,
        name=task.name,
        task=task.task,
        extra_context=task.extra_context,
        model=task.model,
        use_documents=task.use_documents,
        target_kind=task.target_kind,
        target_ref=task.target_ref,
        agent_names=json.loads(task.agent_names or "[]"),
        schedule_kind=task.schedule_kind,
        schedule_human=human,
        run_at=task.run_at,
        interval_minutes=task.interval_minutes,
        time_of_day=task.time_of_day,
        day_of_week=task.day_of_week,
        cron=task.cron,
        timezone=task.timezone,
        enabled=task.enabled,
        status=task.status,
        next_run_at=task.next_run_at,
        last_run_at=task.last_run_at,
        last_status=task.last_status,
        last_execution_id=task.last_execution_id,
        run_count=task.run_count,
        created_at=task.created_at,
    )


def task_to_detail(task: ScheduledTask) -> ScheduledTaskDetail:
    base = task_to_out(task)
    runs = [ScheduledRunOut.model_validate(run) for run in task.runs]
    return ScheduledTaskDetail(**base.model_dump(), runs=runs)
