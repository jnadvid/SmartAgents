"""Servicio documental: subida, extracción, chunking y búsqueda."""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.base import BaseLLMProvider, LLMProviderError
from app.models import Document, DocumentChunk
from app.rag.chunker import chunk_text
from app.rag.document_loader import (
    DocumentProcessingError,
    compute_text_hash,
    content_type_for,
    extract_text,
    store_original_file,
    validate_upload,
)
from app.rag.retriever import ChunkHit, retrieve_relevant, search_chunks

logger = logging.getLogger(__name__)


class DuplicateDocumentError(Exception):
    """El documento (mismo hash de texto) ya existe."""

    def __init__(self, existing: Document) -> None:
        self.existing = existing
        super().__init__(f"Documento duplicado: ya existe con id={existing.id}")


def save_uploaded_document(
    db: Session,
    filename: str,
    raw: bytes,
    provider: BaseLLMProvider | None = None,
    embed_model: str | None = None,
) -> tuple[Document, int]:
    """Valida, extrae texto, trocea e indexa un documento. Devuelve (doc, n_chunks).

    Si se pasa `provider` y `embed_model`, intenta generar embeddings
    (best-effort: si Ollama no está disponible, el documento queda igualmente
    indexado para búsqueda por palabras clave).
    """
    validate_upload(filename, len(raw))
    text = extract_text(filename, raw)
    text_hash = compute_text_hash(text)

    existing = db.execute(
        select(Document).where(Document.text_hash == text_hash)
    ).scalar_one_or_none()
    if existing is not None:
        raise DuplicateDocumentError(existing)

    stored_path = store_original_file(filename, raw)
    document = Document(
        filename=filename,
        path=str(stored_path),
        content_type=content_type_for(filename),
        text_hash=text_hash,
    )
    db.add(document)
    db.flush()

    chunks = chunk_text(text)
    if not chunks:
        raise DocumentProcessingError("El documento no produjo ningún chunk de texto.")
    for index, content in enumerate(chunks):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=content,
                embedding_model=None,  # MVP: búsqueda por keywords; embeddings en roadmap
                metadata_json=json.dumps({"chars": len(content)}, ensure_ascii=False),
            )
        )
    db.commit()
    logger.info(
        "Documento indexado",
        extra={"extra_data": {"document_id": document.id, "chunks": len(chunks)}},
    )

    if provider is not None and embed_model:
        try:
            from app.rag import embeddings

            embeddings.index_document(db, provider, document.id, embed_model)
        except LLMProviderError as exc:
            logger.warning(
                "Embeddings no generados (se usará búsqueda por palabras clave): %s", exc
            )

    return document, len(chunks)


def reindex_embeddings(
    db: Session, provider: BaseLLMProvider, embed_model: str
) -> dict[str, int | str]:
    """Regenera los embeddings de todos los documentos."""
    from app.rag import embeddings

    return embeddings.reindex_all(db, provider, embed_model)


def list_documents(db: Session, limit: int = 100) -> list[Document]:
    stmt = select(Document).order_by(Document.id.desc()).limit(min(limit, 500))
    return list(db.execute(stmt).scalars())


def get_document(db: Session, document_id: int) -> Document | None:
    return db.get(Document, document_id)


def get_document_preview(db: Session, document: Document, max_chars: int = 600) -> str:
    first_chunk = db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
        .limit(1)
    ).scalar_one_or_none()
    return (first_chunk.content[:max_chars] if first_chunk else "").strip()


def count_chunks(db: Session, document_id: int) -> int:
    stmt = select(DocumentChunk.id).where(DocumentChunk.document_id == document_id)
    return len(list(db.execute(stmt).scalars()))


def search_documents(
    db: Session,
    query: str,
    top_k: int = 5,
    mode: str = "keyword",
    provider: BaseLLMProvider | None = None,
    embed_model: str | None = None,
) -> list[ChunkHit]:
    """Búsqueda de documentos por palabras clave, semántica o híbrida."""
    if mode == "keyword" or provider is None or not embed_model:
        return search_chunks(db, query, top_k)
    if mode == "semantic":
        from app.rag import embeddings

        try:
            if embeddings.has_embeddings(db, embed_model):
                return embeddings.semantic_search(db, provider, query, top_k, embed_model)
        except LLMProviderError as exc:
            logger.warning("Búsqueda semántica no disponible: %s", exc)
        return search_chunks(db, query, top_k)
    # hybrid
    return retrieve_relevant(
        db, query, top_k, provider=provider, embed_model=embed_model, use_embeddings=True
    )
