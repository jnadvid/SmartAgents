"""Conectores de archivo: Wazuh local, JSON y CSV (solo lectura, sandbox)."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.connectors.base import (
    BaseConnector,
    ConnectorContext,
    ConnectorError,
    ConnectorResult,
    resolve_sandboxed,
    resolve_source,
)

_MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB de cota de lectura


def _read_text(path: Path) -> str:
    if not path.exists():
        raise ConnectorError(
            f"No existe el archivo de la fuente: {path.name}. "
            "Crea el archivo o ajusta la ruta del conector."
        )
    if path.stat().st_size > _MAX_FILE_BYTES:
        raise ConnectorError(f"El archivo supera el máximo de {_MAX_FILE_BYTES // (1024 * 1024)} MB.")
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_records(text: str) -> list[dict[str, Any]]:
    """Acepta un array JSON, un objeto JSON o NDJSON (un objeto por línea)."""
    stripped = text.strip()
    if not stripped:
        return []
    try:
        data = json.loads(stripped)
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            return [data]
    except json.JSONDecodeError:
        pass
    records: list[dict[str, Any]] = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                records.append(obj)
        except json.JSONDecodeError:
            continue
    return records


def _severity_from_level(level: int | None) -> str:
    if level is None:
        return "unknown"
    if level >= 12:
        return "critical"
    if level >= 7:
        return "high"
    if level >= 4:
        return "medium"
    return "low"


def _normalize_wazuh(alert: dict[str, Any]) -> dict[str, Any]:
    rule = alert.get("rule") or {}
    agent = alert.get("agent") or {}
    data = alert.get("data") or {}
    mitre = rule.get("mitre") or {}
    try:
        level = int(rule.get("level")) if rule.get("level") is not None else None
    except (TypeError, ValueError):
        level = None
    return {
        "id": alert.get("id"),
        "timestamp": alert.get("timestamp"),
        "rule_id": rule.get("id"),
        "level": level,
        "severity": _severity_from_level(level),
        "description": rule.get("description"),
        "groups": rule.get("groups") or [],
        "mitre_ids": mitre.get("id") or [],
        "mitre_tactics": mitre.get("tactic") or [],
        "agent": agent.get("name"),
        "agent_ip": agent.get("ip"),
        "src_ip": data.get("srcip") or data.get("src_ip"),
        "src_user": data.get("srcuser") or data.get("dstuser"),
        "location": alert.get("location"),
    }


# ---------------------------------------------------------------------------
# wazuh_alerts
# ---------------------------------------------------------------------------


class WazuhAlertsInput(BaseModel):
    path: str | None = Field(default=None, description="Ruta al alerts.json (vacío = configuración/sandbox)")
    min_level: int = Field(default=0, ge=0, le=16, description="Nivel mínimo de regla")
    rule_group: str | None = Field(default=None, description="Filtra por grupo de regla (substring)")
    limit: int = Field(default=50, ge=1, le=500)


class WazuhAlertsConnector(BaseConnector):
    name = "wazuh_alerts"
    display_name = "Alertas Wazuh"
    category = "cybersecurity"
    description = (
        "Lee alertas de Wazuh (alerts.json, NDJSON o array) desde un archivo local y "
        "las normaliza (regla, nivel→severidad, MITRE, agente, IPs)."
    )
    input_schema = WazuhAlertsInput

    def read(self, payload: WazuhAlertsInput, ctx: ConnectorContext) -> ConnectorResult:
        from app.config import get_settings

        configured = get_settings().wazuh_alerts_path or None
        source_path = resolve_source(
            ctx, payload.path or configured, "wazuh/alerts.json", allow_absolute=True
        )
        text = _read_text(source_path)
        raw = _parse_records(text)
        records: list[dict[str, Any]] = []
        for alert in raw:
            normalized = _normalize_wazuh(alert)
            if normalized["level"] is not None and normalized["level"] < payload.min_level:
                continue
            if payload.rule_group and payload.rule_group.lower() not in " ".join(
                str(g).lower() for g in normalized["groups"]
            ):
                continue
            records.append(normalized)
            if len(records) >= payload.limit:
                break
        return ConnectorResult(
            connector_name=self.name,
            status="success",
            records=records,
            source=source_path.name,
            summary=f"{len(records)} alerta(s) Wazuh (nivel ≥ {payload.min_level}) desde {source_path.name}.",
        )


# ---------------------------------------------------------------------------
# local_json
# ---------------------------------------------------------------------------


class LocalJsonInput(BaseModel):
    path: str = Field(min_length=1, description="Ruta relativa dentro de data/connectors")
    limit: int = Field(default=100, ge=1, le=1000)


class LocalJsonConnector(BaseConnector):
    name = "local_json"
    display_name = "JSON local"
    category = "general"
    description = "Lee un archivo JSON (array, objeto o NDJSON) desde data/connectors."
    input_schema = LocalJsonInput

    def read(self, payload: LocalJsonInput, ctx: ConnectorContext) -> ConnectorResult:
        source_path = resolve_sandboxed(ctx, payload.path)
        records = _parse_records(_read_text(source_path))[: payload.limit]
        return ConnectorResult(
            connector_name=self.name,
            status="success",
            records=records,
            source=payload.path,
            summary=f"{len(records)} registro(s) JSON desde {payload.path}.",
        )


# ---------------------------------------------------------------------------
# local_csv
# ---------------------------------------------------------------------------


class LocalCsvInput(BaseModel):
    path: str = Field(min_length=1, description="Ruta relativa dentro de data/connectors")
    delimiter: str = Field(default=",", max_length=1)
    limit: int = Field(default=200, ge=1, le=2000)


class LocalCsvConnector(BaseConnector):
    name = "local_csv"
    display_name = "CSV local"
    category = "data"
    description = "Lee un archivo CSV desde data/connectors y devuelve filas como registros."
    input_schema = LocalCsvInput

    def read(self, payload: LocalCsvInput, ctx: ConnectorContext) -> ConnectorResult:
        source_path = resolve_sandboxed(ctx, payload.path)
        text = _read_text(source_path)
        reader = csv.DictReader(io.StringIO(text), delimiter=payload.delimiter or ",")
        records: list[dict[str, Any]] = []
        for row in reader:
            records.append({k: v for k, v in row.items() if k is not None})
            if len(records) >= payload.limit:
                break
        return ConnectorResult(
            connector_name=self.name,
            status="success",
            records=records,
            source=payload.path,
            summary=f"{len(records)} fila(s) CSV desde {payload.path}.",
        )
