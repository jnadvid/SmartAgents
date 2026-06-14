"""Tests del descubrimiento de subdominios (OSINT pasivo + documentos)."""
from __future__ import annotations

from app.osint import subdomains as osint
from app.pentest.runners import RunContext


# ---------------------------------------------------------------------------
# Normalización y validación de dominio
# ---------------------------------------------------------------------------


def test_normalize_domain_strips_scheme_port_path() -> None:
    assert osint.normalize_domain("https://API.Example.com:443/path?x=1") == "api.example.com"
    assert osint.normalize_domain("  Example.COM.  ") == "example.com"
    assert osint.normalize_domain("*.example.com") == "example.com"


def test_normalize_domain_rejects_invalid() -> None:
    for bad in ["", "no spaces here", "localhost", "a..b.com", "http://", "foo;rm -rf"]:
        assert osint.normalize_domain(bad) is None, bad


# ---------------------------------------------------------------------------
# Extracción de subdominios de texto (documentos / salida de herramientas)
# ---------------------------------------------------------------------------


def test_extracts_subdomains_and_dedupes() -> None:
    text = "api.example.com\nMAIL.example.com\napi.example.com\nweb.dev.example.com"
    assert osint.subdomains_in_text(text, "example.com") == {
        "api.example.com", "mail.example.com", "web.dev.example.com",
    }


def test_does_not_capture_foreign_or_extended_domains() -> None:
    # 'a.example.com.evil.com' es de evil.com; 'example.community' no es example.com.
    text = "a.example.com.evil.com example.community b.example.computer"
    assert osint.subdomains_in_text(text, "example.com") == set()


def test_accepts_trailing_sentence_dot_and_urls() -> None:
    text = "Mira https://vpn.example.com/login y también ftp.example.com. Fin."
    assert osint.subdomains_in_text(text, "example.com") == {"vpn.example.com", "ftp.example.com"}


def test_apex_domain_is_not_a_subdomain() -> None:
    assert osint.subdomains_in_text("example.com and www.example.com", "example.com") == {
        "www.example.com",
    }


# ---------------------------------------------------------------------------
# Fusión de fuentes
# ---------------------------------------------------------------------------


def test_merge_sources_unions_attribution_and_sorts() -> None:
    merged = osint.merge_sources({
        "crt.sh": {"b.x.com", "a.x.com"},
        "doc:informe.pdf": {"b.x.com", "c.x.com"},
        "subfinder": {"a.x.com"},
    })
    names = [m.name for m in merged]
    assert names == ["a.x.com", "b.x.com", "c.x.com"]  # ordenado por dominio invertido
    by_name = {m.name: m.sources for m in merged}
    assert by_name["a.x.com"] == ["crt.sh", "subfinder"]
    assert by_name["b.x.com"] == ["crt.sh", "doc:informe.pdf"]


# ---------------------------------------------------------------------------
# crt.sh (HTTP mockeado) y herramientas (subprocess mockeado)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _FakeClient:
    def __init__(self, data):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url):
        return _FakeResponse(self._data)


def test_from_crtsh_parses_filters_and_strips_wildcards(monkeypatch) -> None:
    data = [
        {"name_value": "*.example.com\napi.example.com"},
        {"name_value": "mail.example.com"},
        {"name_value": "otro.dominio.com"},   # se descarta (no es del dominio)
        {"name_value": "example.com"},        # apex: no es subdominio
    ]
    monkeypatch.setattr(osint.httpx, "Client", lambda *a, **k: _FakeClient(data))
    assert osint.from_crtsh("example.com") == {"api.example.com", "mail.example.com"}


def test_from_crtsh_returns_empty_on_http_error(monkeypatch) -> None:
    def _boom(*a, **k):
        raise osint.httpx.HTTPError("sin red")

    monkeypatch.setattr(osint.httpx, "Client", _boom)
    assert osint.from_crtsh("example.com") == set()


def test_from_tools_runs_only_available_and_parses_output(monkeypatch) -> None:
    monkeypatch.setattr(osint.runners, "is_available", lambda ctx, b: b in ("subfinder", "findomain"))
    outputs = {
        "subfinder": "api.example.com\nweb.example.com\n",
        "findomain": "web.example.com\nvpn.example.com\n",
    }
    monkeypatch.setattr(osint, "_run_capture", lambda ctx, b, args, t: outputs.get(b, ""))
    res = osint.from_tools(RunContext(mode="wsl"), "example.com")
    assert set(res) == {"subfinder", "findomain"}  # amass no incluido por defecto
    assert res["subfinder"] == {"api.example.com", "web.example.com"}
    assert res["findomain"] == {"web.example.com", "vpn.example.com"}


def test_from_tools_includes_amass_when_requested(monkeypatch) -> None:
    monkeypatch.setattr(osint.runners, "is_available", lambda ctx, b: b == "amass")
    monkeypatch.setattr(osint, "_run_capture", lambda ctx, b, args, t: "x.example.com" if b == "amass" else "")
    res = osint.from_tools(RunContext(mode="wsl"), "example.com", use_amass=True)
    assert res == {"amass": {"x.example.com"}}
