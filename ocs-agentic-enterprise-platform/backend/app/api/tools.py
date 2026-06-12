"""Endpoints del catálogo de herramientas."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.schemas import ToolCategoriesResponse, ToolInfo
from app.security.auth import api_key_auth
from app.services.agent_runner import get_tool_registry

router = APIRouter(prefix="/tools", tags=["tools"], dependencies=[Depends(api_key_auth)])


@router.get("", response_model=list[ToolInfo])
def list_tools() -> list[ToolInfo]:
    registry = get_tool_registry()
    return [ToolInfo(**tool.describe()) for tool in registry.list_tools()]


@router.get("/categories", response_model=ToolCategoriesResponse)
def tool_categories() -> ToolCategoriesResponse:
    return ToolCategoriesResponse(categories=get_tool_registry().categories())
