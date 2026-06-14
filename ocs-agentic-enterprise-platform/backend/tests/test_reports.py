"""Tests del informe corporativo y del instalador de herramientas."""
from __future__ import annotations

import time

from app import runtime_config
from app.notifications import report as report_builder
from app.pentest.findings import Finding


def test_corporate_report_includes_brand_and_findings() -> None:
    runtime_config.set_overlay({"company_name": "ACME Security", "report_footer": "Confidencial"})
    html = report_builder.pentest_report_html(
        host="app.example.com", profile="web",
        report_markdown="# Resumen\n- **crítico** detectado\n\n## Detalle\ntexto",
        max_severity="critical", by_severity={"critical": 1, "high": 2},
        findings=[Finding("nuclei", "critical", "Log4Shell", "CVE-2021-44228", 9.5)],
    )
    assert "ACME Security" in html
    assert "Informe de Test de Intrusión" in html
    assert "app.example.com" in html
    assert "Log4Shell" in html and "CVE-2021-44228" in html
    assert "Confidencial" in html
    assert "<h1>" in html and "<li>" in html  # markdown renderizado


def test_md_renderer_handles_code_and_headings() -> None:
    html = report_builder._md_to_html("## Título\n```\ncode\n```\ntexto **fuerte**")
    assert "<h2>Título</h2>" in html
    assert "<pre><code>" in html and "code" in html
    assert "<strong>fuerte</strong>" in html


def test_installer_runs_and_captures_log(monkeypatch) -> None:
    from app.pentest import installer as inst

    class FakePopen:
        def __init__(self, *args, **kwargs):
            # En modo binario (sin text=) Popen.stdout itera BYTES.
            self.stdout = iter([b"[*] instalando nmap\n", b"    [ok] nmap\n"])
            self.stdin = None
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(inst.subprocess, "Popen", FakePopen)
    installer = inst.ToolInstaller()
    ok, _ = installer.start(mode="native", wsl_distro="kali-linux")
    assert ok is True
    # Segundo arranque rechazado mientras corre / acaba muy rápido.
    for _ in range(50):
        if not installer.state.running:
            break
        time.sleep(0.02)
    assert installer.state.returncode == 0
    assert "nmap" in installer.state.log
