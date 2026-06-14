"""Endpoints de conectores de datos: catálogo y vista previa de lectura."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.connectors.base import ConnectorContext
from app.schemas import (
    ConnectorCategoriesResponse,
    ConnectorInfo,
    ConnectorReadRequest,
    ConnectorReadResponse,
)
from app.security.auth import api_key_auth
from app.services.agent_runner import get_connector_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connectors", tags=["connectors"], dependencies=[Depends(api_key_auth)])


def _enabled(requires_network: bool) -> bool:
    return (not requires_network) or get_settings().enable_http_connectors


@router.get("", response_model=list[ConnectorInfo])
def list_connectors() -> list[ConnectorInfo]:
    registry = get_connector_registry()
    out: list[ConnectorInfo] = []
    for connector in registry.list_connectors():
        info = connector.describe()
        out.append(ConnectorInfo(enabled=_enabled(info["requires_network"]), **info))
    return out


@router.get("/categories", response_model=ConnectorCategoriesResponse)
def connector_categories() -> ConnectorCategoriesResponse:
    return ConnectorCategoriesResponse(categories=get_connector_registry().categories())


@router.post("/{name}/read", response_model=ConnectorReadResponse)
def read_connector(name: str, request: ConnectorReadRequest) -> ConnectorReadResponse:
    """Vista previa: lee el conector directamente (acción del operador, sin agente)."""
    registry = get_connector_registry()
    if registry.get(name) is None:
        raise HTTPException(status_code=404, detail=f"Conector desconocido: '{name}'.")
    result = registry.read(name, request.params, ConnectorContext(agent_name="operator"), allowed_connectors=None)
    return ConnectorReadResponse(
        connector=result.connector_name,
        status=result.status,
        count=result.count,
        summary=result.summary,
        source=result.source,
        records=result.records[: request.max_records],
        error_message=result.error_message,
    )
