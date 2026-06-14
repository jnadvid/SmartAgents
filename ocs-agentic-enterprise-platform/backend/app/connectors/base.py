"""Conectores de datos: lectura controlada de fuentes para los agentes.

Un conector LEE datos de una fuente (archivo local de alertas Wazuh, JSON/CSV
local o, opcionalmente, un endpoint HTTP de la allow-list) y los normaliza a
una lista de registros que se inyecta como contexto a un agente o equipo.

Modelo de seguridad:
- Solo LECTURA. Nunca escriben ni ejecutan nada.
- Los conectores de archivo solo leen dentro de `backend/data/connectors`
  (con protección contra path traversal). La excepción es la ruta del
  alerts.json de Wazuh, que el operador puede fijar explícitamente por
  configuración (es su propia máquina).
- Los conectores HTTP están DESACTIVADOS por defecto y, si se activan, solo
  permiten hosts de la allow-list.
- Cada agente declara su `data_access` (allow-list de conectores). El registro
  deniega cualquier lectura fuera de esa lista.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from app.security.sanitization import redact_secrets, summarize_for_log, truncate

logger = logging.getLogger(__name__)


class ConnectorError(Exception):
    """Error controlado de un conector."""


@dataclass
class ConnectorContext:
    """Contexto de ejecución de un conector (inyectable para tests)."""

    base_dir: Path | None = None  # raíz de conectores (por defecto backend/data/connectors)
    agent_name: str | None = None


@dataclass
class ConnectorResult:
    """Resultado normalizado de una lectura de conector."""

    connector_name: str
    status: str  # success | error | denied | disabled
    records: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    source: str = ""
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "success"

    @property
    def count(self) -> int:
        return len(self.records)

    def to_context_block(self, max_records: int = 50, max_chars: int = 8000) -> str:
        """Renderiza los registros como bloque de contexto seguro para el LLM."""
        if not self.ok or not self.records:
            return ""
        lines = [f"## DATOS DE LA FUENTE [conector: {self.connector_name}] ({self.count} registro(s))"]
        if self.source:
            lines.append(f"Origen: {self.source}")
        for index, record in enumerate(self.records[:max_records], start=1):
            rendered = json.dumps(record, ensure_ascii=False, default=str)
            lines.append(f"{index}. {truncate(redact_secrets(rendered), 600)}")
        block = "\n".join(lines)
        return truncate(block, max_chars)


# ---------------------------------------------------------------------------
# Resolución segura de rutas
# ---------------------------------------------------------------------------


def _connectors_base(ctx: ConnectorContext) -> Path:
    if ctx.base_dir is not None:
        return ctx.base_dir
    from app.config import get_settings

    return get_settings().connectors_dir


def resolve_sandboxed(ctx: ConnectorContext, relative: str) -> Path:
    """Resuelve una ruta SIEMPRE dentro del directorio de conectores (anti traversal)."""
    base = _connectors_base(ctx).resolve()
    target = (base / relative).resolve()
    if base != target and base not in target.parents:
        raise ConnectorError(f"Ruta '{relative}' fuera del directorio de conectores permitido.")
    return target


def resolve_source(ctx: ConnectorContext, path: str | None, default_relative: str, *, allow_absolute: bool) -> Path:
    """Resuelve la fuente: relativa (sandbox) o absoluta (solo si allow_absolute)."""
    if not path:
        return resolve_sandboxed(ctx, default_relative)
    candidate = Path(path)
    if candidate.is_absolute():
        if not allow_absolute:
            raise ConnectorError("Las rutas absolutas no están permitidas en este conector.")
        return candidate.resolve()
    return resolve_sandboxed(ctx, path)


# ---------------------------------------------------------------------------
# Conector base
# ---------------------------------------------------------------------------


class BaseConnector(ABC):
    """Conector base: valida la entrada y normaliza la salida (nunca lanza)."""

    name: str = "base_connector"
    display_name: str = "Conector base"
    category: str = "general"
    description: str = ""
    requires_network: bool = False
    input_schema: type[BaseModel]

    @abstractmethod
    def read(self, payload: BaseModel, ctx: ConnectorContext) -> ConnectorResult:
        """Lee la fuente. Recibe la entrada ya validada."""

    def run(self, raw_params: dict[str, Any] | None, ctx: ConnectorContext | None = None) -> ConnectorResult:
        ctx = ctx or ConnectorContext()
        try:
            payload = self.input_schema.model_validate(raw_params or {})
        except ValidationError as exc:
            detail = "; ".join(
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
            )
            return ConnectorResult(self.name, "error", error_message=f"Parámetros inválidos: {detail}")
        try:
            return self.read(payload, ctx)
        except ConnectorError as exc:
            return ConnectorResult(self.name, "error", error_message=summarize_for_log(str(exc), 300))
        except Exception as exc:  # noqa: BLE001 - frontera controlada del conector
            logger.exception("Error en el conector %s", self.name)
            return ConnectorResult(self.name, "error", error_message=summarize_for_log(str(exc), 300))

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "category": self.category,
            "description": self.description,
            "requires_network": self.requires_network,
            "input_schema": self.input_schema.model_json_schema(),
        }
