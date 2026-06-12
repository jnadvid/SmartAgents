"""Extracción de texto de documentos subidos (TXT, MD y PDF).

El archivo original se guarda bajo backend/data/documents con un nombre
generado (UUID), nunca con el nombre del usuario: evita colisiones y
path traversal.
"""
from __future__ import annotations

import hashlib
import io
import logging
import uuid
from pathlib import Path

from app.config import get_settings
from app.security.policies import ensure_path_in_data_dir
from app.security.sanitization import clean_text

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}

_CONTENT_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
}


class DocumentProcessingError(Exception):
    """Error al procesar un documento subido."""


def get_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def content_type_for(filename: str) -> str:
    return _CONTENT_TYPES.get(get_extension(filename), "application/octet-stream")


def validate_upload(filename: str, size_bytes: int) -> None:
    """Valida extensión y tamaño antes de procesar."""
    settings = get_settings()
    extension = get_extension(filename)
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise DocumentProcessingError(
            f"Extensión no soportada: '{extension or 'sin extensión'}'. Soportadas: {supported}."
        )
    if size_bytes <= 0:
        raise DocumentProcessingError("El archivo está vacío.")
    if size_bytes > settings.max_document_size_bytes:
        raise DocumentProcessingError(
            f"El archivo supera el máximo de {settings.max_document_size_mb} MB."
        )


def extract_text(filename: str, raw: bytes) -> str:
    """Extrae texto plano del documento según su extensión."""
    extension = get_extension(filename)
    if extension in (".txt", ".md"):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="replace")
    elif extension == ".pdf":
        text = _extract_pdf_text(raw)
    else:
        raise DocumentProcessingError(f"Extensión no soportada: {extension}")

    text = clean_text(text).strip()
    if not text:
        raise DocumentProcessingError(
            "No se pudo extraer texto del documento (¿PDF escaneado sin OCR?)."
        )
    return text


def _extract_pdf_text(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise DocumentProcessingError(
            "Soporte PDF no disponible: instala 'pypdf' (pip install pypdf)."
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001 - pypdf lanza tipos variados
        raise DocumentProcessingError(f"No se pudo leer el PDF: {exc}") from exc
    return "\n\n".join(pages)


def compute_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def store_original_file(filename: str, raw: bytes) -> Path:
    """Guarda el archivo original dentro de backend/data/documents."""
    settings = get_settings()
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    extension = get_extension(filename)
    target = settings.documents_dir / f"{uuid.uuid4().hex}{extension}"
    ensure_path_in_data_dir(target)
    target.write_bytes(raw)
    logger.info(
        "Documento almacenado",
        extra={"extra_data": {"filename": filename, "stored_as": target.name, "bytes": len(raw)}},
    )
    return target
