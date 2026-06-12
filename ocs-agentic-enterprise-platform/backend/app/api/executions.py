"""Endpoints de ejecuciones y Chain-of-Work."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ChainOfWorkResponse,
    ChainOfWorkStepOut,
    ExecutionDetail,
    ExecutionSummary,
)
from app.security.auth import api_key_auth
from app.services import execution_service

router = APIRouter(prefix="/executions", tags=["executions"], dependencies=[Depends(api_key_auth)])


@router.get("", response_model=list[ExecutionSummary])
def list_executions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    agent_name: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[ExecutionSummary]:
    executions = execution_service.list_executions(
        db, limit=limit, offset=offset, agent_name=agent_name, status=status
    )
    return [ExecutionSummary.model_validate(e) for e in executions]


@router.get("/{execution_id}", response_model=ExecutionDetail)
def get_execution(execution_id: int, db: Session = Depends(get_db)) -> ExecutionDetail:
    execution = execution_service.get_execution(db, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail=f"Ejecución {execution_id} no encontrada.")
    return ExecutionDetail.model_validate(execution)


@router.get("/{execution_id}/chain-of-work", response_model=ChainOfWorkResponse)
def get_chain_of_work(execution_id: int, db: Session = Depends(get_db)) -> ChainOfWorkResponse:
    execution = execution_service.get_execution(db, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail=f"Ejecución {execution_id} no encontrada.")
    steps = execution_service.get_chain_of_work(db, execution_id)
    return ChainOfWorkResponse(
        execution_id=execution_id,
        steps=[ChainOfWorkStepOut.model_validate(step) for step in steps],
    )
