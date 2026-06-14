"""Conector HTTP JSON (opt-in, allow-list de hosts).

Desactivado por defecto. Solo se usa si ENABLE_HTTP_CONNECTORS=true y el host
del endpoint está en HTTP_CONNECTOR_ALLOWLIST. Pensado para fuentes propias y
autorizadas (p. ej. la API de Wazuh en la red local). No sigue redirecciones.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from app.connectors.base import BaseConnector, ConnectorContext, ConnectorError, ConnectorResult

_MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class HttpJsonInput(BaseModel):
    url: str = Field(min_length=8, max_length=2000, description="URL del endpoint JSON (host en allow-list)")
    list_key: str | None = Field(default=None, description="Clave cuyo valor es la lista de registros")
    limit: int = Field(default=100, ge=1, le=1000)


class HttpJsonConnector(BaseConnector):
    name = "http_json"
    display_name = "HTTP JSON (opt-in)"
    category = "general"
    description = (
        "Lee JSON de un endpoint HTTP de la allow-list (desactivado por defecto). "
        "Para fuentes propias y autorizadas, p. ej. la API local de Wazuh."
    )
    requires_network = True
    input_schema = HttpJsonInput

    def read(self, payload: HttpJsonInput, ctx: ConnectorContext) -> ConnectorResult:
        from app.config import get_settings

        settings = get_settings()
        if not settings.enable_http_connectors:
            raise ConnectorError("Los conectores HTTP están desactivados (ENABLE_HTTP_CONNECTORS=false).")

        parsed = urlparse(payload.url)
        if parsed.scheme not in ("http", "https"):
            raise ConnectorError("Solo se permiten URLs http/https.")
        host = (parsed.hostname or "").lower()
        allow = settings.http_connector_hosts
        if host not in allow:
            raise ConnectorError(
                f"Host '{host}' no está en la allow-list de conectores HTTP. "
                "Añádelo a HTTP_CONNECTOR_ALLOWLIST."
            )

        import httpx

        try:
            with httpx.Client(timeout=settings.connector_timeout, follow_redirects=False) as client:
                response = client.get(payload.url)
                response.raise_for_status()
                if len(response.content) > _MAX_RESPONSE_BYTES:
                    raise ConnectorError("La respuesta supera el tamaño máximo permitido.")
                data = response.json()
        except httpx.HTTPError as exc:
            raise ConnectorError(f"Error HTTP al leer la fuente: {exc}") from exc

        if payload.list_key and isinstance(data, dict):
            data = data.get(payload.list_key, [])
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            raise ConnectorError("La respuesta JSON no es una lista ni un objeto de registros.")
        records = [r for r in data if isinstance(r, dict)][: payload.limit]
        return ConnectorResult(
            connector_name=self.name,
            status="success",
            records=records,
            source=host,
            summary=f"{len(records)} registro(s) JSON desde {host}.",
        )
