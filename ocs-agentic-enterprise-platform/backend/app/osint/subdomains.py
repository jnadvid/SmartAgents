"""Descubrimiento y consolidación de subdominios (OSINT pasivo + documentos).

Construye la lista MÁS COMPLETA posible de subdominios de un dominio combinando
varias fuentes y deduplicando:

  - Certificate Transparency (crt.sh): pasivo, solo HTTP, sin herramientas.
  - Herramientas de Kali si están instaladas (subfinder, assetfinder, findomain,
    amass en modo pasivo). Se ejecutan por el runner robusto (WSL/nativo).
  - Subdominios extraídos de documentos que sube el usuario (informes, listados,
    salidas de otras herramientas… TXT/MD/CSV/JSON/etc. y PDF).

Opcionalmente resuelve por DNS cuáles están vivos y su IP. Todo es OSINT pasivo
y no intrusivo: no se envía tráfico de ataque al objetivo.
"""
from __future__ import annotations

import logging
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import httpx

from app.pentest import runners
from app.pentest.runners import RunContext

logger = logging.getLogger(__name__)

# Dominio válido (sin esquema ni puerto). Acotado para evitar ReDoS.
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.){1,8}[a-z]{2,63}$"
)
# Una etiqueta DNS.
_LABEL = r"[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?"

# Herramientas de descubrimiento (binario, fn(dominio)->args, timeout segundos).
# Todas en modo PASIVO. amass es opcional porque puede ser lento.
_TOOLS: list[tuple[str, object, int]] = [
    ("subfinder", lambda d: ["-silent", "-all", "-d", d], 180),
    ("assetfinder", lambda d: ["--subs-only", d], 120),
    ("findomain", lambda d: ["-t", d, "-q"], 120),
]
_AMASS = ("amass", lambda d: ["enum", "-passive", "-d", d], 300)


def normalize_domain(raw: str) -> str | None:
    """Normaliza y valida un dominio: minúsculas, sin esquema/puerto/ruta. None si inválido."""
    d = (raw or "").strip().lower()
    if "://" in d:
        d = d.split("://", 1)[1]
    d = d.split("/", 1)[0].split("?", 1)[0]
    d = d.split(":", 1)[0].strip().strip(".")
    if d.startswith("*."):
        d = d[2:]
    if not d or not _DOMAIN_RE.match(d):
        return None
    return d


def _pattern_for(domain: str) -> re.Pattern[str]:
    esc = re.escape(domain)
    # Una etiqueta o más, luego el dominio. Los lookaheads rechazan que el host
    # CONTINÚE (alnum, '-', o '.'+alnum) para no capturar 'a.dominio.com' dentro de
    # 'a.dominio.com.otro.com', pero sí aceptan un punto final de frase 'dominio.com.'.
    return re.compile(
        rf"(?<![a-z0-9._-])((?:{_LABEL}\.){{1,12}}{esc})(?![a-z0-9\-])(?!\.[a-z0-9])",
        re.IGNORECASE,
    )


def subdomains_in_text(text: str, domain: str) -> set[str]:
    """Extrae todos los subdominios de `domain` presentes en `text` (cualquier formato)."""
    if not text:
        return set()
    found: set[str] = set()
    for match in _pattern_for(domain).finditer(text):
        host = match.group(1).lower().strip(".")
        if host != domain and host.endswith("." + domain) and len(host) <= 253:
            found.add(host)
    return found


def from_crtsh(domain: str, *, timeout: int = 25) -> set[str]:
    """Subdominios desde Certificate Transparency (crt.sh). Pasivo, solo HTTP."""
    url = f"https://crt.sh/?q=%25.{domain}&output=json"
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True,
                          headers={"User-Agent": "OCS-OSINT/1.0"}) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("crt.sh no disponible para %s: %s", domain, exc)
        return set()
    found: set[str] = set()
    for entry in data if isinstance(data, list) else []:
        for name in str(entry.get("name_value", "")).splitlines():
            host = name.strip().lower().lstrip("*.").strip(".")
            if host != domain and host.endswith("." + domain) and _DOMAIN_RE.match(host):
                found.add(host)
    return found


def _run_capture(ctx: RunContext, binary: str, args: list[str], timeout: int) -> str:
    """Ejecuta una herramienta de descubrimiento y devuelve su salida (vacío si falla)."""
    argv, stdin = runners.build_invocation(ctx, binary, args)
    if argv is None:
        return ""
    try:
        proc = subprocess.run(  # noqa: S603 - argv controlado por el runner
            argv, shell=False, capture_output=True, input=stdin, timeout=timeout, check=False,
        )
        return (proc.stdout or b"").decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        logger.info("%s superó el timeout de %ss para subdominios", binary, timeout)
        return ""
    except Exception as exc:  # noqa: BLE001 - frontera controlada
        logger.warning("Fallo ejecutando %s: %s", binary, exc)
        return ""


def from_tools(ctx: RunContext, domain: str, *, use_amass: bool = False) -> dict[str, set[str]]:
    """Ejecuta las herramientas pasivas instaladas y devuelve {herramienta: subdominios}."""
    tools = list(_TOOLS) + ([_AMASS] if use_amass else [])
    results: dict[str, set[str]] = {}
    for binary, argf, timeout in tools:
        if not runners.is_available(ctx, binary):
            continue
        out = _run_capture(ctx, binary, argf(domain), timeout)  # type: ignore[operator]
        subs = subdomains_in_text(out, domain)
        if subs:
            results[binary] = subs
    return results


def resolve_many(hosts: list[str], *, workers: int = 40, timeout: float = 3.0) -> dict[str, str | None]:
    """Resuelve por DNS (concurrente). Devuelve {host: ip o None}."""
    if not hosts:
        return {}
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        def _one(host: str) -> tuple[str, str | None]:
            try:
                return host, socket.gethostbyname(host)
            except OSError:
                return host, None

        with ThreadPoolExecutor(max_workers=min(workers, max(1, len(hosts)))) as pool:
            return dict(pool.map(_one, hosts))
    finally:
        socket.setdefaulttimeout(old)


@dataclass
class Subdomain:
    name: str
    sources: list[str] = field(default_factory=list)
    resolved: bool | None = None
    ip: str | None = None


@dataclass
class SourceInfo:
    source: str
    count: int
    ok: bool
    detail: str = ""


def merge_sources(by_source: dict[str, set[str]]) -> list[Subdomain]:
    """Funde {fuente: subdominios} en una lista única ordenada con atribución de fuentes."""
    all_sources: dict[str, set[str]] = {}
    for source, subs in by_source.items():
        for sub in subs:
            all_sources.setdefault(sub, set()).add(source)
    result = [Subdomain(name=name, sources=sorted(src)) for name, src in all_sources.items()]
    result.sort(key=lambda s: tuple(reversed(s.name.split("."))))
    return result


def attach_resolution(subdomains: list[Subdomain]) -> None:
    """Rellena resolved/ip de cada subdominio (in-place) consultando DNS."""
    resolution = resolve_many([s.name for s in subdomains])
    for sub in subdomains:
        ip = resolution.get(sub.name)
        sub.resolved = ip is not None
        sub.ip = ip
