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
    method: str = "keyword"


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


def retrieve_relevant(
    db: Session,
    query: str,
    top_k: int = 5,
    provider=None,
    embed_model: str | None = None,
    use_embeddings: bool = False,
) -> list[ChunkHit]:
    """Recuperación híbrida (Fase 2): keyword + semántica (si está disponible).

    Degradación elegante: si los embeddings están desactivados, no hay índice
    o el proveedor falla, devuelve la búsqueda por palabras clave.
    """
    keyword_hits = search_chunks(db, query, top_k)

    if not use_embeddings or provider is None or not embed_model:
        return keyword_hits

    # Import local: el módulo de embeddings es opcional para el resto del sistema.
    from app.llm.base import LLMProviderError
    from app.rag import embeddings as emb

    if not emb.has_embeddings(db, embed_model):
        return keyword_hits
    try:
        vector_hits = emb.semantic_search(db, provider, query, top_k, embed_model)
    except LLMProviderError as exc:
        logger.warning("Búsqueda semántica no disponible, se usa keyword: %s", exc)
        return keyword_hits

    if not vector_hits:
        return keyword_hits
    return _merge_hits(keyword_hits, vector_hits, top_k)


def _merge_hits(
    keyword_hits: list[ChunkHit], vector_hits: list[ChunkHit], top_k: int
) -> list[ChunkHit]:
    """Combina resultados keyword y semánticos en una puntuación 0-1 ponderada."""
    from app.config import get_settings

    weight = get_settings().rag_vector_weight
    max_keyword = max((h.score for h in keyword_hits), default=0.0) or 1.0

    combined: dict[tuple[int, int], dict] = {}
    for hit in keyword_hits:
        key = (hit.document_id, hit.chunk_index)
        combined[key] = {"hit": hit, "kw": hit.score / max_keyword, "vec": 0.0}
    for hit in vector_hits:
        key = (hit.document_id, hit.chunk_index)
        entry = combined.setdefault(key, {"hit": hit, "kw": 0.0, "vec": 0.0})
        entry["vec"] = hit.score
        # Preferimos el snippet semántico (más centrado en el significado).
        entry["hit"] = hit

    results: list[ChunkHit] = []
    for entry in combined.values():
        score = weight * entry["vec"] + (1.0 - weight) * entry["kw"]
        base = entry["hit"]
        method = "hybrid" if entry["kw"] > 0 and entry["vec"] > 0 else base.method
        results.append(
            ChunkHit(
                document_id=base.document_id,
                filename=base.filename,
                chunk_index=base.chunk_index,
                score=round(score, 4),
                snippet=base.snippet,
                content=base.content,
                method=method,
            )
        )
    results.sort(key=lambda h: -h.score)
    return results[:top_k]


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
