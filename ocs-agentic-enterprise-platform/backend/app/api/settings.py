"""Endpoints de ajustes editables en runtime (modelo, pentest, WSL, email)."""
from __future__ import annotations

import logging
import platform
import shutil

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import runtime_config
from app.database import get_db
from app.notifications import email as email_service
from app.schemas import EmailTestRequest, SettingsOut, SettingsUpdate
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
    pub = runtime_config.public_effective()
    return SettingsOut(
        default_ollama_model=str(pub["default_ollama_model"]),
        enable_pentest_tools=bool(pub["enable_pentest_tools"]),
        pentest_scope_allowlist=str(pub["pentest_scope_allowlist"]),
        pentest_execution_mode=str(pub["pentest_execution_mode"]),
        pentest_wsl_distro=str(pub["pentest_wsl_distro"]),
        pentest_wsl_user=str(pub["pentest_wsl_user"]),
        pentest_wsl_password_set=bool(pub["pentest_wsl_password_set"]),
        smtp_host=str(pub["smtp_host"]),
        smtp_port=int(pub["smtp_port"]),
        smtp_user=str(pub["smtp_user"]),
        smtp_from=str(pub["smtp_from"]),
        smtp_use_tls=bool(pub["smtp_use_tls"]),
        smtp_password_set=bool(pub["smtp_password_set"]),
        notify_email=str(pub["notify_email"]),
        company_name=str(pub["company_name"]),
        report_logo_url=str(pub["report_logo_url"]),
        report_footer=str(pub["report_footer"]),
        host_os=platform.system() or "unknown",
        wsl_available=shutil.which("wsl") is not None,
        email_configured=email_service.is_configured(),
        available_models=_available_models(),
    )


@router.get("", response_model=SettingsOut)
def get_settings_endpoint() -> SettingsOut:
    return _build_out()


@router.put("", response_model=SettingsOut)
def update_settings_endpoint(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsOut:
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    # En secretos, un valor vacío significa "no cambiar" (no se borra el existente).
    for secret in runtime_config.SECRET_KEYS:
        if secret in changes and not str(changes[secret]).strip():
            changes.pop(secret)
    if changes:
        try:
            runtime_config.persist(db, changes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        logger.info("Ajustes actualizados", extra={"extra_data": {"keys": sorted(changes)}})
    return _build_out()


@router.post("/test-email")
def test_email(request: EmailTestRequest) -> dict[str, object]:
    """Envía un email de prueba con la configuración SMTP actual."""
    ok, message = email_service.send_email(
        to=request.to,
        subject="OCS Agentic Platform · prueba de email",
        html="<h2>Prueba correcta ✅</h2><p>La configuración SMTP de la plataforma funciona.</p>",
        text="Prueba correcta. La configuración SMTP de la plataforma funciona.",
    )
    return {"ok": ok, "message": message}
