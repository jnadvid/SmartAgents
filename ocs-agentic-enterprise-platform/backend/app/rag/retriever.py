"""Recuperación de chunks por palabras clave sobre SQLite (MVP).

Estrategia: prefiltro SQL con LIKE por token y reordenación en Python por
frecuencia de términos + bonus de frase exacta. Devuelve citas con
documento, índice de chunk y fragmento.

Futuro (roadmap): índice vectorial con embeddings de Ollama + ChromaDB.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.security.sanitization import normalize_for_matching
from app.tools._text_utils import make_snippet, tokenize

logger = logging.getLogger(__name__)

_MAX_QUERY_TOKENS = 8
_MAX_CANDIDATES = 500


@dataclass(frozen=True)
class ChunkHit:
    document_id: int
    filename: str
    chunk_index: int
    score: float
    snippet: str
    content: str


def search_chunks(db: Session, query: str, top_k: int = 5) -> list[ChunkHit]:
    """Busca los chunks más relevantes para la consulta."""
    tokens = tokenize(query)[:_MAX_QUERY_TOKENS]
    if not tokens:
        return []

    stmt = (
        select(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(or_(*(DocumentChunk.content.ilike(f"%{token}%") for token in tokens)))
        .limit(_MAX_CANDIDATES)
    )
    rows = db.execute(stmt).all()
    if not rows:
        return []

    normalized_query = normalize_for_matching(query)
    hits: list[ChunkHit] = []
    for chunk, document in rows:
        normalized_content = normalize_for_matching(chunk.content)
        score = float(sum(normalized_content.count(token) for token in tokens))
        if normalized_query and normalized_query in normalized_content:
            score += 5.0  # bonus por frase exacta
        if score <= 0:
            continue
        best_token = max(tokens, key=lambda t: normalized_content.count(t))
        hits.append(
            ChunkHit(
                document_id=document.id,
                filename=document.filename,
                chunk_index=chunk.chunk_index,
                score=score,
                snippet=make_snippet(chunk.content, best_token, 300),
                content=chunk.content,
            )
        )

    hits.sort(key=lambda h: -h.score)
    logger.debug(
        "Búsqueda RAG completada",
        extra={"extra_data": {"query_tokens": tokens, "hits": len(hits)}},
    )
    return hits[:top_k]


def build_context_block(hits: list[ChunkHit], max_chars: int = 6000) -> str:
    """Bloque de contexto citable para inyectar en el prompt del agente."""
    if not hits:
        return ""
    parts: list[str] = []
    used = 0
    for hit in hits:
        fragment = hit.content[:1500]
        entry = (
            f"[Documento: {hit.filename} | chunk {hit.chunk_index} | "
            f"relevancia {hit.score:.1f}]\n{fragment}"
        )
        if used + len(entry) > max_chars:
            break
        parts.append(entry)
        used += len(entry)
    return "\n\n---\n\n".join(parts)
