"""Tests de ajustes editables en runtime y modos de ejecución (nativo/WSL)."""
from __future__ import annotations

import pytest

from app import runtime_config
from app.pentest import runners
from app.pentest.runners import RunContext


def test_persist_and_reload(db_session) -> None:
    assert runtime_config.effective("enable_pentest_tools") is False  # default del .env
    runtime_config.persist(db_session, {
        "enable_pentest_tools": True,
        "default_ollama_model": "phi3:mini",
        "pentest_scope_allowlist": "midominio.com, 10.0.0.0/24",
        "pentest_execution_mode": "wsl",
    })
    assert runtime_config.effective("enable_pentest_tools") is True
    assert runtime_config.effective("default_ollama_model") == "phi3:mini"
    assert runtime_config.scope_entries() == ["midominio.com", "10.0.0.0/24"]
    assert runtime_config.effective("pentest_execution_mode") == "wsl"

    # Recarga desde la BD reconstruye el overlay.
    runtime_config.reset()
    assert runtime_config.effective("enable_pentest_tools") is False  # overlay vacío
    runtime_config.load(db_session)
    assert runtime_config.effective("enable_pentest_tools") is True


def test_validate_rejects_non_editable_and_bad_values() -> None:
    with pytest.raises(ValueError, match="no editable"):
        runtime_config.validate({"secret_key": "x"})
    with pytest.raises(ValueError, match="native"):
        runtime_config.validate({"pentest_execution_mode": "hacker"})
    # Coerción de booleano desde string.
    assert runtime_config.validate({"enable_pentest_tools": "true"})["enable_pentest_tools"] is True
    assert runtime_config.validate({"enable_pentest_tools": "no"})["enable_pentest_tools"] is False


def test_wsl_command_is_prefixed(monkeypatch) -> None:
    monkeypatch.setattr(runners, "is_available", lambda ctx, binary: True)
    argv = runners.build_argv(RunContext(mode="wsl", wsl_distro="kali-linux"), "nmap", ["-sV", "host"])
    assert argv == ["wsl", "-d", "kali-linux", "--", "nmap", "-sV", "host"]


def test_native_command_resolves_path() -> None:
    argv = runners.build_argv(RunContext(mode="native"), "true", ["x"])  # 'true' existe en Linux
    assert argv is not None and argv[0].endswith("true") and argv[-1] == "x"
    # Binario inexistente -> None
    assert runners.build_argv(RunContext(mode="native"), "binario_que_no_existe_xyz", []) is None
