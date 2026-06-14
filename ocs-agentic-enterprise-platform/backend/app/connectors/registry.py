"""Registro de conectores con enforcement del acceso de lectura por agente."""
from __future__ import annotations

import logging
from typing import Any, Iterable

from app.connectors.base import BaseConnector, ConnectorContext, ConnectorResult

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """Catálogo de conectores; única vía de lectura, con allow-list por agente."""

    def __init__(self) -> None:
        self._connectors: dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector) -> None:
        if connector.name in self._connectors:
            raise ValueError(f"Conector duplicado en el registro: '{connector.name}'")
        self._connectors[connector.name] = connector

    def register_all(self, connectors: Iterable[BaseConnector]) -> None:
        for connector in connectors:
            self.register(connector)

    def get(self, name: str) -> BaseConnector | None:
        return self._connectors.get(name)

    def names(self) -> list[str]:
        return sorted(self._connectors)

    def list_connectors(self) -> list[BaseConnector]:
        return [self._connectors[name] for name in self.names()]

    def categories(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for connector in self.list_connectors():
            result.setdefault(connector.category, []).append(connector.name)
        return result

    def read(
        self,
        name: str,
        params: dict[str, Any] | None,
        ctx: ConnectorContext | None = None,
        allowed_connectors: list[str] | None = None,
    ) -> ConnectorResult:
        """Lee un conector aplicando el acceso de lectura del agente.

        Si `allowed_connectors` no es None, el conector debe estar incluido; en
        caso contrario se devuelve 'denied'. Los conectores de red se devuelven
        como 'disabled' si ENABLE_HTTP_CONNECTORS es false.
        """
        connector = self._connectors.get(name)
        if connector is None:
            return ConnectorResult(name, "error", error_message=f"Conector desconocido: '{name}'.")
        if allowed_connectors is not None and name not in allowed_connectors:
            logger.warning(
                "Lectura de conector denegada por acceso",
                extra={"extra_data": {"connector": name, "agent": ctx.agent_name if ctx else None}},
            )
            return ConnectorResult(
                name, "denied",
                error_message="El agente no tiene acceso de lectura a este conector (data_access).",
            )
        if connector.requires_network:
            from app.config import get_settings

            if not get_settings().enable_http_connectors:
                return ConnectorResult(
                    name, "disabled",
                    error_message="Conector de red desactivado (ENABLE_HTTP_CONNECTORS=false).",
                )
        return connector.run(params, ctx)


def build_default_connector_registry() -> ConnectorRegistry:
    """Construye el registro con los conectores disponibles."""
    from app.connectors.file_connectors import (
        LocalCsvConnector,
        LocalJsonConnector,
        WazuhAlertsConnector,
    )
    from app.connectors.http_connectors import HttpJsonConnector

    registry = ConnectorRegistry()
    registry.register_all(
        [
            WazuhAlertsConnector(),
            LocalJsonConnector(),
            LocalCsvConnector(),
            HttpJsonConnector(),
        ]
    )
    return registry
