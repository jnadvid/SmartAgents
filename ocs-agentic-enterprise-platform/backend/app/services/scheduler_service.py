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
from app.connectors.base import ConnectorContext
from app.connectors.registry import ConnectorRegistry
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


def _involved_agent_names(target_kind: str, target_ref: str | None, agent_names_json: str) -> list[str]:
    """Agentes que recibirán los datos del conector (para validar el acceso)."""
    if target_kind == "agent":
        return [target_ref] if target_ref else []
    if target_kind == "team":
        return [n for n in json.loads(agent_names_json or "[]") if n]
    if target_kind == "squad":
        from app.services.agent_runner import get_squad_registry

        squad = get_squad_registry().get(target_ref or "")
        return list(squad.members) if squad else []
    return []  # auto


def _common_data_access(agent_names: list[str], agent_registry: AgentRegistry) -> set[str]:
    """Intersección del data_access de los agentes implicados."""
    sets: list[set[str]] = []
    for name in agent_names:
        agent = agent_registry.get(name)
        sets.append(set(agent.data_access) if agent else set())
    if not sets:
        return set()
    common = set(sets[0])
    for extra in sets[1:]:
        common &= extra
    return common


def _validate_connector(
    target_kind: str,
    target_ref: str | None,
    agent_names_json: str,
    connector: str | None,
    agent_registry: AgentRegistry,
) -> None:
    """Valida el conector y que TODOS los agentes implicados tengan acceso de lectura."""
    if not connector:
        return
    from app.services.agent_runner import get_connector_registry

    if get_connector_registry().get(connector) is None:
        raise ValueError(f"Conector desconocido: '{connector}'.")
    if target_kind == "auto":
        raise ValueError("Para usar un conector elige un agente, squad o equipo concreto (no 'auto').")
    involved = _involved_agent_names(target_kind, target_ref, agent_names_json)
    if not involved:
        raise ValueError("No se pudieron resolver los agentes del objetivo para validar el acceso al conector.")
    lacking = [
        name for name in involved
        if connector not in (agent_registry.get(name).data_access if agent_registry.get(name) else [])
    ]
    if lacking:
        raise ValueError(
            f"Estos agentes no tienen acceso de lectura al conector '{connector}': {', '.join(lacking)}. "
            "Revisa su data_access."
        )


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
    _validate_connector(
        payload.target_kind, payload.target_ref,
        json.dumps(payload.agent_names or [], ensure_ascii=False), payload.connector, agent_registry,
    )

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
        connector=payload.connector,
        connector_params=json.dumps(payload.connector_params or {}, ensure_ascii=False),
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
                  "day_of_week", "cron", "timezone", "target_kind", "connector"):
        if field in data and data[field] is not None:
            setattr(task, field, data[field])
    if "agent_names" in data and data["agent_names"] is not None:
        task.agent_names = json.dumps(data["agent_names"], ensure_ascii=False)
    if "connector_params" in data and data["connector_params"] is not None:
        task.connector_params = json.dumps(data["connector_params"], ensure_ascii=False)

    # Validar objetivo, conector y programación tras los cambios.
    _validate_target(
        task.target_kind, task.target_ref, json.loads(task.agent_names or "[]"),
        agent_registry, squad_names,
    )
    _validate_connector(task.target_kind, task.target_ref, task.agent_names, task.connector, agent_registry)
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


def _dispatch(task: ScheduledTask, runner: AgentRunner, extra_context: str | None):
    """Ejecuta la tarea según su objetivo y devuelve la ExecutionResponse."""
    if task.target_kind == "squad":
        return runner.execute_squad(
            SquadExecuteRequest(
                task=task.task, squad_name=task.target_ref or None, model=task.model,
                use_documents=task.use_documents, extra_context=extra_context,
            )
        )
    if task.target_kind == "team":
        return runner.execute_squad(
            SquadExecuteRequest(
                task=task.task, agent_names=json.loads(task.agent_names or "[]"), model=task.model,
                use_documents=task.use_documents, extra_context=extra_context,
            )
        )
    # agent o auto
    return runner.execute(
        ExecuteRequest(
            task=task.task, agent_name=(task.target_ref or None) if task.target_kind == "agent" else None,
            model=task.model, use_documents=task.use_documents, extra_context=extra_context,
        )
    )


def _read_connector(
    task: ScheduledTask, *, agent_registry: AgentRegistry, connector_registry: ConnectorRegistry
):
    """Lee el conector de la tarea respetando el data_access. Devuelve ConnectorResult o None."""
    if not task.connector:
        return None
    involved = _involved_agent_names(task.target_kind, task.target_ref, task.agent_names)
    allowed = list(_common_data_access(involved, agent_registry))
    params = json.loads(task.connector_params or "{}")
    return connector_registry.read(
        task.connector, params,
        ConnectorContext(agent_name=task.target_ref or "scheduler"),
        allowed_connectors=allowed,
    )


def _finish_run(
    db: Session, task: ScheduledTask, started: datetime, *, status: str, message: str, execution_id: int | None
) -> ScheduledRun:
    """Registra el run, actualiza la tarea y calcula la siguiente ejecución."""
    finished = utcnow()
    run = ScheduledRun(
        scheduled_task_id=task.id,
        execution_id=execution_id,
        status=status,
        message=summarize_for_log(message, 500),
        started_at=started,
        finished_at=finished,
    )
    db.add(run)

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


def execute_one(
    db: Session,
    task: ScheduledTask,
    *,
    llm: BaseLLMProvider,
    tool_registry: ToolRegistry,
    agent_registry: AgentRegistry,
    session_factory,
    connector_registry: ConnectorRegistry | None = None,
) -> ScheduledRun:
    """Ejecuta una tarea programada una vez (leyendo su conector si lo tiene)."""
    started = utcnow()
    if connector_registry is None:
        from app.services.agent_runner import get_connector_registry

        connector_registry = get_connector_registry()

    # 1. Leer el conector (si lo hay) respetando el data_access de los agentes.
    extra_context = task.extra_context
    connector_note = ""
    if task.connector:
        result = _read_connector(task, agent_registry=agent_registry, connector_registry=connector_registry)
        if result is None or not result.ok:
            reason = (result.error_message if result else "sin resultado") or (result.status if result else "")
            return _finish_run(
                db, task, started, status="error",
                message=f"conector {task.connector}: {reason}", execution_id=None,
            )
        connector_note = f"conector {task.connector}: {result.count} registro(s)"
        if result.count == 0:
            return _finish_run(
                db, task, started, status="skipped",
                message=f"{connector_note} (sin datos: no se ejecuta)", execution_id=None,
            )
        block = result.to_context_block()
        extra_context = ((task.extra_context or "") + "\n\n" + block).strip()

    # 2. Ejecutar el agente / equipo.
    runner = AgentRunner(
        db, llm=llm, tool_registry=tool_registry,
        agent_registry=agent_registry, session_factory=session_factory,
    )
    execution_id: int | None = None
    status = "completed"
    message = ""
    try:
        response = _dispatch(task, runner, extra_context)
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

    if connector_note:
        message = (connector_note + (" · " + message if message else "")).strip()
    return _finish_run(db, task, started, status=status, message=message, execution_id=execution_id)


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
    connector_registry: ConnectorRegistry | None = None,
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
                    connector_registry=connector_registry,
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
        connector=task.connector,
        connector_params=json.loads(task.connector_params or "{}"),
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
