"""Endpoints de agentes: catálogo, enrutado y ejecución."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    AgentCategoriesResponse,
    AgentInfo,
    ExecuteRequest,
    ExecutionResponse,
    RouteRequest,
    RouteResponse,
)
from app.security.auth import api_key_auth
from app.security.policies import PolicyViolation
from app.services.agent_runner import AgentRunner, get_agent_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(api_key_auth)])


@router.get("", response_model=list[AgentInfo])
def list_agents() -> list[AgentInfo]:
    registry = get_agent_registry()
    return [AgentInfo(**agent.describe()) for agent in registry.list_agents()]


@router.get("/categories", response_model=AgentCategoriesResponse)
def agent_categories() -> AgentCategoriesResponse:
    return AgentCategoriesResponse(categories=get_agent_registry().categories())


@router.post("/route", response_model=RouteResponse)
def route_task(request: RouteRequest, db: Session = Depends(get_db)) -> RouteResponse:
    """Vista previa del enrutado: clasifica la intención SIN ejecutar nada."""
    runner = AgentRunner(db)
    try:
        return runner.preview_route(request.task)
    except PolicyViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/execute", response_model=ExecutionResponse)
def execute_auto(
    request: ExecuteRequest,
    db: Session = Depends(get_db),
    username: str = Depends(api_key_auth),
) -> ExecutionResponse:
    """Ejecución en modo auto (el router elige agente) o manual si se indica agent_name."""
    return _execute(db, request, username)


@router.post("/{agent_name}/execute", response_model=ExecutionResponse)
def execute_with_agent(
    agent_name: str,
    request: ExecuteRequest,
    db: Session = Depends(get_db),
    username: str = Depends(api_key_auth),
) -> ExecutionResponse:
    """Ejecución en modo manual con el agente indicado en la ruta."""
    request = request.model_copy(update={"agent_name": agent_name})
    return _execute(db, request, username)


def _execute(db: Session, request: ExecuteRequest, username: str) -> ExecutionResponse:
    if request.agent_name and get_agent_registry().get(request.agent_name) is None:
        available = ", ".join(get_agent_registry().names())
        raise HTTPException(
            status_code=404,
            detail=f"Agente desconocido: '{request.agent_name}'. Disponibles: {available}.",
        )
    runner = AgentRunner(db)
    try:
        return runner.execute(request, username=username)
    except PolicyViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
