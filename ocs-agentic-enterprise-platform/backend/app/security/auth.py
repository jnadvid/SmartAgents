"""Autenticación opcional por API key local.

MVP: si ENABLE_AUTH=true, todas las rutas (excepto /health) exigen la
cabecera `X-API-Key` con el valor de SECRET_KEY. Pensado para un único
usuario local; multiusuario con roles queda en el roadmap.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)

LOCAL_USERNAME = "local"


async def api_key_auth(x_api_key: str | None = Header(default=None)) -> str:
    """Dependencia FastAPI: valida la API key si la autenticación está activa.

    Devuelve el nombre del usuario autenticado (MVP: usuario local único).
    """
    settings = get_settings()
    if not settings.enable_auth:
        return LOCAL_USERNAME

    if not x_api_key or not hmac.compare_digest(x_api_key, settings.secret_key):
        logger.warning("Intento de acceso con API key inválida o ausente")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o ausente. Envía la cabecera X-API-Key.",
        )
    return LOCAL_USERNAME
