"""Endpoints de ajustes editables en runtime (modelo por defecto, pentest, WSL)."""
from __future__ import annotations

import logging
import platform
import shutil

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import runtime_config
from app.database import get_db
from app.schemas import SettingsOut, SettingsUpdate
from app.security.auth import api_key_auth
from app.services.agent_runner import get_llm_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(api_key_auth)])


def _available_models() -> list[str]:
    try:
        return sorted(m.name for m in get_llm_provider().list_models())
    except Exception:  # noqa: BLE001 - Ollama puede estar caído
        return []


def _build_out() -> SettingsOut:
    values = runtime_config.all_effective()
    return SettingsOut(
        default_ollama_model=str(values["default_ollama_model"]),
        enable_pentest_tools=bool(values["enable_pentest_tools"]),
        pentest_scope_allowlist=str(values["pentest_scope_allowlist"]),
        pentest_execution_mode=str(values["pentest_execution_mode"]),
        pentest_wsl_distro=str(values["pentest_wsl_distro"]),
        host_os=platform.system() or "unknown",
        wsl_available=shutil.which("wsl") is not None,
        available_models=_available_models(),
    )


@router.get("", response_model=SettingsOut)
def get_settings_endpoint() -> SettingsOut:
    return _build_out()


@router.put("", response_model=SettingsOut)
def update_settings_endpoint(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsOut:
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if changes:
        try:
            runtime_config.persist(db, changes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        logger.info("Ajustes actualizados", extra={"extra_data": {"keys": sorted(changes)}})
    return _build_out()
