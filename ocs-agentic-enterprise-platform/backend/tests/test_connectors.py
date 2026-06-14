"""Tests de conectores de datos, acceso de lectura y scheduler con conector."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.connectors.base import ConnectorContext
from app.connectors.registry import build_default_connector_registry
from app.schemas import ScheduledTaskCreate
from app.services import scheduler_service
from app.services.agent_runner import build_default_squad_registry

UTC = timezone.utc

_ALERTS = [
    {"id": "1", "timestamp": "2026-06-14T08:00:00Z",
     "rule": {"id": "5710", "level": 10, "description": "sshd: Multiple failed logins",
              "groups": ["authentication_failed"], "mitre": {"id": ["T1110"], "tactic": ["Credential Access"]}},
     "agent": {"name": "web-01", "ip": "10.0.0.5"}, "data": {"srcip": "203.0.113.9", "srcuser": "root"}},
    {"id": "2", "timestamp": "2026-06-14T08:01:00Z",
     "rule": {"id": "2502", "level": 3, "description": "Login notice"}, "agent": {"name": "web-01"}},
]


@pytest.fixture()
def wazuh_file(tmp_path) -> Path:
    path = tmp_path / "alerts.json"
    path.write_text("\n".join(json.dumps(a) for a in _ALERTS), encoding="utf-8")
    return path


@pytest.fixture()
def connectors():
    return build_default_connector_registry()


@pytest.fixture()
def squad_names() -> set[str]:
    return set(build_default_squad_registry().names())


# ---------------------------------------------------------------------------
# Conectores
# ---------------------------------------------------------------------------


def test_wazuh_connector_filters_by_level(connectors, wazuh_file) -> None:
    result = connectors.read("wazuh_alerts", {"path": str(wazuh_file), "min_level": 7}, ConnectorContext(),
                             allowed_connectors=["wazuh_alerts"])
    assert result.ok and result.count == 1
    record = result.records[0]
    assert record["mitre_ids"] == ["T1110"] and record["severity"] == "high"
    assert "DATOS DE LA FUENTE" in result.to_context_block()


def test_connector_access_denied_when_not_allowed(connectors, wazuh_file) -> None:
    result = connectors.read("wazuh_alerts", {"path": str(wazuh_file)}, ConnectorContext(),
                             allowed_connectors=["local_json"])
    assert result.status == "denied"


def test_http_connector_disabled_by_default(connectors) -> None:
    result = connectors.read("http_json", {"url": "http://localhost/api"}, ConnectorContext(),
                             allowed_connectors=["http_json"])
    assert result.status == "disabled"


def test_local_json_rejects_path_traversal(connectors) -> None:
    result = connectors.read("local_json", {"path": "../../etc/passwd"}, ConnectorContext(),
                             allowed_connectors=["local_json"])
    assert result.status == "error" and "fuera" in (result.error_message or "").lower()


def test_unknown_connector_returns_error(connectors) -> None:
    result = connectors.read("no_existe", {}, ConnectorContext(), allowed_connectors=None)
    assert result.status == "error" and "desconocido" in (result.error_message or "").lower()


# ---------------------------------------------------------------------------
# Scheduler con conector (acceso de lectura definido)
# ---------------------------------------------------------------------------


def _create_connector_task(db, agent_registry, squad_names, wazuh_file, **overrides):
    payload = {
        "name": "Bucle SOC", "task": "Investiga las alertas y decide.",
        "target_kind": "agent", "target_ref": "blue_team_analyst",
        "connector": "wazuh_alerts", "connector_params": {"path": str(wazuh_file), "min_level": 7},
        "schedule_kind": "once", "run_at": datetime.now(UTC) - timedelta(minutes=1), "model": "fake-model",
    }
    payload.update(overrides)
    return scheduler_service.create_task(
        db, ScheduledTaskCreate(**payload), agent_registry=agent_registry, squad_names=squad_names
    )


def test_create_connector_task_requires_data_access(db_session, agent_registry, squad_names, wazuh_file) -> None:
    # business_assistant no tiene data_access a wazuh_alerts -> rechazo
    with pytest.raises(ValueError, match="acceso de lectura"):
        _create_connector_task(db_session, agent_registry, squad_names, wazuh_file, target_ref="business_assistant")


def test_connector_requires_explicit_target(db_session, agent_registry, squad_names, wazuh_file) -> None:
    with pytest.raises(ValueError, match="no 'auto'"):
        _create_connector_task(db_session, agent_registry, squad_names, wazuh_file, target_kind="auto", target_ref=None)


def test_run_due_reads_connector_and_injects_context(
    db_session, fake_llm, tool_registry, agent_registry, squad_names, memory_session_factory, connectors, wazuh_file
) -> None:
    task = _create_connector_task(db_session, agent_registry, squad_names, wazuh_file)
    runs = scheduler_service.run_due(
        db_session, llm=fake_llm, tool_registry=tool_registry, agent_registry=agent_registry,
        session_factory=memory_session_factory, connector_registry=connectors,
    )
    assert len(runs) == 1
    assert runs[0].status == "completed"
    assert "wazuh_alerts: 1 registro" in runs[0].message
    # La alerta llegó al prompt del agente como contexto de la fuente.
    last_user = next(m["content"] for m in reversed(fake_llm.chat_calls[-1]) if m["role"] == "user")
    assert "DATOS DE LA FUENTE" in last_user and "T1110" in last_user


def test_run_due_skips_when_connector_has_no_data(
    db_session, fake_llm, tool_registry, agent_registry, squad_names, memory_session_factory, connectors, wazuh_file
) -> None:
    # min_level alto -> 0 alertas -> no se ejecuta el agente
    task = _create_connector_task(
        db_session, agent_registry, squad_names, wazuh_file,
        connector_params={"path": str(wazuh_file), "min_level": 15},
    )
    runs = scheduler_service.run_due(
        db_session, llm=fake_llm, tool_registry=tool_registry, agent_registry=agent_registry,
        session_factory=memory_session_factory, connector_registry=connectors,
    )
    assert len(runs) == 1 and runs[0].status == "skipped"
    assert runs[0].execution_id is None
