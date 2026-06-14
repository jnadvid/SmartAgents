"""Descubrimiento de subdominios (OSINT pasivo + documentos).

Consolida subdominios desde Certificate Transparency (crt.sh), herramientas de
Kali pasivas (subfinder, assetfinder, findomain, amass) y documentos subidos por
el usuario, para construir la lista más completa posible de un dominio. Es OSINT
pasivo: no requiere alcance autorizado, pero sí valida el formato del dominio.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.config import get_settings
from app.osint import subdomains as osint
from app.rag import document_loader
from app.schemas import (
    SubdomainEnumerateRequest,
    SubdomainItem,
    SubdomainResolveRequest,
    SubdomainScanResponse,
    SubdomainSourceInfo,
    SubdomainStatusResponse,
    SubdomainToolInfo,
)
from app.security.auth import api_key_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subdomains", tags=["subdomains"], dependencies=[Depends(api_key_auth)])

# Binarios de descubrimiento que reporta el estado.
_TOOL_BINARIES = ["subfinder", "assetfinder", "findomain", "amass"]
# Extensiones de texto que sabemos extraer además de las del document_loader (TXT/MD/PDF).
_EXTRA_TEXT_EXT = {
    ".csv", ".json", ".log", ".out", ".gnmap", ".nmap", ".xml", ".html", ".htm",
    ".tsv", ".list", ".lst", ".text", ".yaml", ".yml", ".ini", ".conf",
}


def _ctx():
    from app import runtime_config
    from app.pentest.runners import RunContext

    return RunContext(
        mode=runtime_config.effective_execution_mode(),
        wsl_distro=str(runtime_config.effective("pentest_wsl_distro")),
        wsl_user=str(runtime_config.effective("pentest_wsl_user")),
    )


def _pentest_enabled() -> bool:
    from app import runtime_config

    return bool(runtime_config.effective("enable_pentest_tools"))


def _require_domain(raw: str) -> str:
    domain = osint.normalize_domain(raw)
    if domain is None:
        raise HTTPException(status_code=400, detail=f"Dominio no válido: '{raw}'.")
    return domain


def _response(domain: str, by_source: dict[str, set[str]], *, resolve: bool) -> SubdomainScanResponse:
    merged = osint.merge_sources(by_source)
    if resolve:
        osint.attach_resolution(merged)
    sources = [
        SubdomainSourceInfo(source=src, count=len(subs), ok=True)
        for src, subs in sorted(by_source.items())
    ]
    return SubdomainScanResponse(
        domain=domain,
        total=len(merged),
        sources=sources,
        subdomains=[
            SubdomainItem(name=s.name, sources=s.sources, resolved=s.resolved, ip=s.ip)
            for s in merged
        ],
    )


@router.get("/status", response_model=SubdomainStatusResponse)
def status() -> SubdomainStatusResponse:
    from app.pentest import runners

    ctx = _ctx()
    enabled = _pentest_enabled()
    if enabled:
        runners.clear_cache()
        avail = runners.check_many(ctx, _TOOL_BINARIES)
    else:
        avail = {b: False for b in _TOOL_BINARIES}
    return SubdomainStatusResponse(
        execution_mode=ctx.mode,
        pentest_enabled=enabled,
        tools=[SubdomainToolInfo(name=b, available=avail.get(b, False)) for b in _TOOL_BINARIES],
    )


@router.post("/enumerate", response_model=SubdomainScanResponse)
def enumerate_subdomains(request: SubdomainEnumerateRequest) -> SubdomainScanResponse:
    domain = _require_domain(request.domain)
    by_source: dict[str, set[str]] = {"crt.sh": osint.from_crtsh(domain)}

    if request.use_tools and _pentest_enabled():
        from app.pentest import runners

        ctx = _ctx()
        runners.clear_cache()
        runners.check_many(ctx, _TOOL_BINARIES)  # detección fresca (una sola llamada a WSL)
        by_source.update(osint.from_tools(ctx, domain, use_amass=request.use_amass))

    logger.info("Enumeración de subdominios", extra={"extra_data": {
        "domain": domain, "sources": {k: len(v) for k, v in by_source.items()}}})
    return _response(domain, by_source, resolve=request.resolve)


@router.post("/extract", response_model=SubdomainScanResponse)
async def extract_from_documents(
    domain: str = Form(...),
    files: list[UploadFile] = File(...),
) -> SubdomainScanResponse:
    domain_clean = _require_domain(domain)
    settings = get_settings()
    by_source: dict[str, set[str]] = {}
    for upload in files:
        filename = upload.filename or "documento"
        raw = await upload.read()
        if not raw:
            continue
        if len(raw) > settings.max_document_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"'{filename}' supera el máximo de {settings.max_document_size_mb} MB.",
            )
        text = _extract_text(filename, raw)
        subs = osint.subdomains_in_text(text, domain_clean)
        if subs:
            by_source[f"doc:{filename}"] = subs
    logger.info("Subdominios desde documentos", extra={"extra_data": {
        "domain": domain_clean, "files": len(files), "found": sum(len(v) for v in by_source.values())}})
    return _response(domain_clean, by_source, resolve=False)


@router.post("/resolve", response_model=SubdomainScanResponse)
def resolve_subdomains(request: SubdomainResolveRequest) -> SubdomainScanResponse:
    domain = _require_domain(request.domain)
    valid = sorted({
        n.strip().lower() for n in request.names
        if n.strip().lower().endswith("." + domain) or n.strip().lower() == domain
    })
    resolution = osint.resolve_many(valid)
    items = [
        SubdomainItem(name=name, sources=[], resolved=(ip is not None), ip=ip)
        for name, ip in sorted(resolution.items())
    ]
    return SubdomainScanResponse(domain=domain, total=len(items), sources=[], subdomains=items)


def _extract_text(filename: str, raw: bytes) -> str:
    """Texto del documento. Reutiliza el loader (TXT/MD/PDF) y acepta otros formatos de texto."""
    ext = document_loader.get_extension(filename)
    if ext == ".pdf":
        try:
            return document_loader.extract_text(filename, raw)
        except document_loader.DocumentProcessingError as exc:
            logger.info("No se pudo extraer texto de %s: %s", filename, exc)
            return ""
    # Cualquier otro formato: lo tratamos como texto (subfinder/nmap/csv/json…).
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")
