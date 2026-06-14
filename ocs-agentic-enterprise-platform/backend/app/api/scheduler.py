"""Endpoints del programador de tareas (scheduler local)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models import ScheduledTask
from app.schemas import (
    ScheduledRunOut,
    ScheduledTaskCreate,
    ScheduledTaskDetail,
    ScheduledTaskOut,
    ScheduledTaskUpdate,
    SchedulerStatusResponse,
)
from app.scheduler.runner import get_scheduler
from app.security.auth import api_key_auth
from app.security.policies import PolicyViolation
from app.services import scheduler_service
from app.services.agent_runner import (
    get_agent_registry,
    get_connector_registry,
    get_llm_provider,
    get_squad_registry,
    get_tool_registry,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduler", tags=["scheduler"], dependencies=[Depends(api_key_auth)])


def _squad_names() -> set[str]:
    return set(get_squad_registry().names())


@router.post("/tasks", response_model=ScheduledTaskOut, status_code=status.HTTP_201_CREATED)
def create_scheduled_task(
    payload: ScheduledTaskCreate, db: Session = Depends(get_db)
) -> ScheduledTaskOut:
    try:
        task = scheduler_service.create_task(
            db, payload, agent_registry=get_agent_registry(), squad_names=_squad_names()
        )
    except (ValueError, PolicyViolation) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return scheduler_service.task_to_out(task)


@router.get("/tasks", response_model=list[ScheduledTaskOut])
def list_scheduled_tasks(
    enabled: bool | None = Query(default=None), db: Session = Depends(get_db)
) -> list[ScheduledTaskOut]:
    return [scheduler_service.task_to_out(t) for t in scheduler_service.list_tasks(db, enabled=enabled)]


@router.get("/status", response_model=SchedulerStatusResponse)
def scheduler_status(db: Session = Depends(get_db)) -> SchedulerStatusResponse:
    settings = get_settings()
    total = db.execute(select(func.count()).select_from(ScheduledTask)).scalar_one()
    active = db.execute(
        select(func.count()).select_from(ScheduledTask).where(ScheduledTask.enabled.is_(True))
    ).scalar_one()
    next_run = db.execute(
        select(func.min(ScheduledTask.next_run_at)).where(ScheduledTask.enabled.is_(True))
    ).scalar_one()
    return SchedulerStatusResponse(
        enabled=settings.enable_scheduler,
        running=get_scheduler().running,
        poll_seconds=settings.scheduler_poll_seconds,
        total_tasks=int(total or 0),
        active_tasks=int(active or 0),
        next_run_at=next_run,
    )


@router.get("/tasks/{task_id}", response_model=ScheduledTaskDetail)
def get_scheduled_task(task_id: int, db: Session = Depends(get_db)) -> ScheduledTaskDetail:
    task = scheduler_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Tarea programada {task_id} no encontrada.")
    return scheduler_service.task_to_detail(task)


@router.patch("/tasks/{task_id}", response_model=ScheduledTaskOut)
def update_scheduled_task(
    task_id: int, payload: ScheduledTaskUpdate, db: Session = Depends(get_db)
) -> ScheduledTaskOut:
    task = scheduler_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Tarea programada {task_id} no encontrada.")
    try:
        task = scheduler_service.update_task(
            db, task, payload, agent_registry=get_agent_registry(), squad_names=_squad_names()
        )
    except (ValueError, PolicyViolation) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return scheduler_service.task_to_out(task)


@router.post("/tasks/{task_id}/pause", response_model=ScheduledTaskOut)
def pause_scheduled_task(task_id: int, db: Session = Depends(get_db)) -> ScheduledTaskOut:
    task = scheduler_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Tarea programada {task_id} no encontrada.")
    return scheduler_service.task_to_out(scheduler_service.set_enabled(db, task, False))


@router.post("/tasks/{task_id}/resume", response_model=ScheduledTaskOut)
def resume_scheduled_task(task_id: int, db: Session = Depends(get_db)) -> ScheduledTaskOut:
    task = scheduler_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Tarea programada {task_id} no encontrada.")
    try:
        updated = scheduler_service.set_enabled(db, task, True)
    except (ValueError, PolicyViolation) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return scheduler_service.task_to_out(updated)


@router.post("/tasks/{task_id}/run-now", response_model=ScheduledRunOut)
def run_scheduled_task_now(task_id: int, db: Session = Depends(get_db)) -> ScheduledRunOut:
    """Dispara la tarea inmediatamente (síncrono) y reprograma la siguiente."""
    task = scheduler_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Tarea programada {task_id} no encontrada.")
    run = scheduler_service.execute_one(
        db, task,
        llm=get_llm_provider(),
        tool_registry=get_tool_registry(),
        agent_registry=get_agent_registry(),
        session_factory=SessionLocal,
        connector_registry=get_connector_registry(),
    )
    return ScheduledRunOut.model_validate(run)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scheduled_task(task_id: int, db: Session = Depends(get_db)) -> Response:
    task = scheduler_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Tarea programada {task_id} no encontrada.")
    scheduler_service.delete_task(db, task)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
