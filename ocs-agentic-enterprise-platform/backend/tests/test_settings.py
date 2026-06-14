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


def test_wsl_command_is_piped_via_stdin(monkeypatch) -> None:
    monkeypatch.setattr(runners, "is_available", lambda ctx, binary: True)
    # En WSL el comando va por STDIN a `sh -s` (no como argumentos de wsl.exe).
    argv, stdin = runners.build_invocation(RunContext(mode="wsl", wsl_distro="kali-linux"), "nmap", ["-sV", "host"])
    assert argv == ["wsl", "-d", "kali-linux", "--", "sh", "-s"]
    assert b"export PATH=" in stdin and b"nmap -sV host" in stdin


def test_native_command_resolves_path() -> None:
    argv, stdin = runners.build_invocation(RunContext(mode="native"), "true", ["x"])  # 'true' existe en Linux
    assert argv is not None and argv[0].endswith("true") and argv[-1] == "x" and stdin is None
    # Binario inexistente -> (None, None)
    assert runners.build_invocation(RunContext(mode="native"), "binario_que_no_existe_xyz", []) == (None, None)


def test_wsl_command_includes_user(monkeypatch) -> None:
    monkeypatch.setattr(runners, "is_available", lambda ctx, binary: True)
    argv, _ = runners.build_invocation(RunContext(mode="wsl", wsl_distro="kali-linux", wsl_user="kali"), "nmap", ["host"])
    assert argv[:5] == ["wsl", "-d", "kali-linux", "-u", "kali"] and argv[-2:] == ["sh", "-s"]


def test_wsl_root_password_goes_through_pipe_not_argv(monkeypatch) -> None:
    monkeypatch.setattr(runners, "is_available", lambda ctx, binary: True)
    ctx = RunContext(mode="wsl", wsl_distro="kali-linux")
    argv, stdin = runners.build_invocation(ctx, "nmap", ["-sS", "host"], needs_root=True, sudo_password="s3cr3t")
    assert argv == ["wsl", "-d", "kali-linux", "--", "sh", "-s"]
    # La contraseña va en el script (por stdin), nunca en los argumentos de wsl.exe.
    assert b"s3cr3t" not in b" ".join(a.encode() for a in argv)
    assert b"sudo -S" in stdin and b"s3cr3t" in stdin


def test_check_many_and_probe_native() -> None:
    # En nativo, check_many usa el PATH del host (sin subprocess de WSL).
    res = runners.check_many(RunContext(mode="native"), ["true", "binario_inexistente_xyz"])
    assert res["true"] is True and res["binario_inexistente_xyz"] is False
    ok, msg = runners.probe_environment(RunContext(mode="native"))
    assert ok is True and "nativo" in msg.lower()


def test_secrets_never_exposed(db_session) -> None:
    runtime_config.persist(db_session, {"smtp_password": "supersecreta", "smtp_host": "smtp.x", "smtp_from": "a@b.com"})
    public = runtime_config.public_effective()
    assert "smtp_password" not in public and "pentest_wsl_password" not in public
    assert public["smtp_password_set"] is True
    # El valor real sigue disponible internamente para enviar emails.
    assert runtime_config.effective("smtp_password") == "supersecreta"


def test_empty_secret_keeps_existing(db_session) -> None:
    runtime_config.persist(db_session, {"smtp_password": "clave1"})
    # Simula el comportamiento de la API: vacío en un secreto = no cambiar.
    changes = {"smtp_password": ""}
    for secret in runtime_config.SECRET_KEYS:
        if secret in changes and not str(changes[secret]).strip():
            changes.pop(secret)
    assert changes == {}
    assert runtime_config.effective("smtp_password") == "clave1"
