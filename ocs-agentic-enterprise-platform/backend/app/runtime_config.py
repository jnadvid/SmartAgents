"""Ajustes editables en runtime.

Mantiene un overlay en memoria (de proceso) que sobrescribe los valores del
`.env` para un conjunto acotado de claves (modelo por defecto, pentest, modo de
ejecución). Se carga desde la BD al arrancar y se refresca al guardar desde la
API. Las claves NO incluidas aquí (auth, rutas, etc.) nunca son editables.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

# Allow-list de claves editables y su tipo.
EDITABLE: dict[str, type] = {
    "default_ollama_model": str,
    "enable_pentest_tools": bool,
    "pentest_scope_allowlist": str,
    "pentest_execution_mode": str,
    "pentest_wsl_distro": str,
}
_MODES = ("native", "wsl")

_overlay: dict[str, Any] = {}


def _env_defaults() -> dict[str, Any]:
    s = get_settings()
    return {
        "default_ollama_model": s.default_ollama_model,
        "enable_pentest_tools": s.enable_pentest_tools,
        "pentest_scope_allowlist": s.pentest_scope_allowlist,
        "pentest_execution_mode": s.pentest_execution_mode,
        "pentest_wsl_distro": s.pentest_wsl_distro,
    }


def effective(key: str, default: Any = None) -> Any:
    """Valor efectivo: overlay si existe, si no el del .env."""
    if key in _overlay:
        return _overlay[key]
    return _env_defaults().get(key, default)


def all_effective() -> dict[str, Any]:
    values = _env_defaults()
    values.update({k: v for k, v in _overlay.items() if k in EDITABLE})
    return values


def scope_entries() -> list[str]:
    raw = str(effective("pentest_scope_allowlist") or "")
    return [entry.strip().lower() for entry in raw.split(",") if entry.strip()]


def _coerce(key: str, value: Any) -> Any:
    expected = EDITABLE[key]
    if expected is bool:
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on", "si", "sí")
        return bool(value)
    if expected is str:
        return "" if value is None else str(value)
    return value


def validate(changes: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in changes.items():
        if key not in EDITABLE:
            raise ValueError(f"Ajuste no editable: '{key}'.")
        coerced = _coerce(key, value)
        if key == "pentest_execution_mode" and coerced not in _MODES:
            raise ValueError("pentest_execution_mode debe ser 'native' o 'wsl'.")
        if key == "pentest_wsl_distro" and not str(coerced).replace("-", "").replace(".", "").replace("_", "").isalnum():
            raise ValueError("Nombre de distribución WSL inválido.")
        clean[key] = coerced
    return clean


def set_overlay(values: dict[str, Any]) -> None:
    """Actualiza el overlay en memoria (sin persistir). Útil en tests."""
    for key, value in values.items():
        if key in EDITABLE:
            _overlay[key] = value


def load(db) -> None:
    """Carga el overlay desde la BD (al arrancar)."""
    from sqlalchemy import select

    from app.models import AppSetting

    _overlay.clear()
    for row in db.execute(select(AppSetting)).scalars():
        if row.key in EDITABLE:
            try:
                _overlay[row.key] = json.loads(row.value)
            except (json.JSONDecodeError, TypeError):
                continue
    logger.info("Ajustes de runtime cargados", extra={"extra_data": {"keys": sorted(_overlay)}})


def persist(db, changes: dict[str, Any]) -> dict[str, Any]:
    """Valida, persiste en la BD y refresca el overlay. Devuelve los valores efectivos."""
    from app.models import AppSetting

    clean = validate(changes)
    for key, value in clean.items():
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=json.dumps(value)))
        else:
            row.value = json.dumps(value)
    db.commit()
    set_overlay(clean)
    return all_effective()


def reset() -> None:
    """Limpia el overlay (tests)."""
    _overlay.clear()
