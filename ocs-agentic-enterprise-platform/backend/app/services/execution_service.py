"""Consultas sobre ejecuciones y su Chain-of-Work."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentExecution, ChainOfWorkStep


def list_executions(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    agent_name: str | None = None,
    status: str | None = None,
) -> list[AgentExecution]:
    stmt = select(AgentExecution).order_by(AgentExecution.id.desc())
    if agent_name:
        stmt = stmt.where(AgentExecution.agent_name == agent_name)
    if status:
        stmt = stmt.where(AgentExecution.status == status)
    stmt = stmt.limit(min(limit, 200)).offset(max(offset, 0))
    return list(db.execute(stmt).scalars())


def get_execution(db: Session, execution_id: int) -> AgentExecution | None:
    return db.get(AgentExecution, execution_id)


def get_chain_of_work(db: Session, execution_id: int) -> list[ChainOfWorkStep]:
    stmt = (
        select(ChainOfWorkStep)
        .where(ChainOfWorkStep.execution_id == execution_id)
        .order_by(ChainOfWorkStep.step_number)
    )
    return list(db.execute(stmt).scalars())


def delete_execution(db: Session, execution_id: int) -> bool:
    """Borra una ejecución y, en cascada, sus pasos, logs y ruta. Devuelve si existía."""
    execution = db.get(AgentExecution, execution_id)
    if execution is None:
        return False
    db.delete(execution)
    db.commit()
    return True


def delete_executions(db: Session, *, status: str | None = None) -> int:
    """Borra ejecuciones (opcionalmente filtradas por estado). Devuelve cuántas se borraron."""
    stmt = select(AgentExecution)
    if status:
        stmt = stmt.where(AgentExecution.status == status)
    executions = list(db.execute(stmt).scalars())
    for execution in executions:
        db.delete(execution)
    db.commit()
    return len(executions)
