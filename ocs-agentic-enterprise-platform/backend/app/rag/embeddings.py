"""RAG semántico (Fase 2): embeddings locales con Ollama sobre SQLite.

Estrategia local y sin dependencias cloud:
- Los vectores se generan con un modelo de embeddings de Ollama
  (`nomic-embed-text` por defecto) y se guardan como JSON en la tabla
  `chunk_embeddings`.
- La búsqueda semántica calcula similitud coseno en Python puro (suficiente
  para la escala local del MVP; un índice vectorial dedicado queda en roadmap).

Todo es best-effort: si Ollama o el modelo de embeddings no están disponibles,
la plataforma sigue funcionando con la búsqueda por palabras clave.
"""
from __future__ import annotations

import json
import logging
import math
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.llm.base import BaseLLMProvider, LLMProviderError
from app.models import ChunkEmbedding, Document, DocumentChunk
from app.tools._text_utils import make_snippet

if TYPE_CHECKING:
    from app.rag.retriever import ChunkHit

logger = logging.getLogger(__name__)

_EMBED_BATCH = 32


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Similitud coseno entre dos vectores. Devuelve 0.0 si alguno es nulo."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def has_embeddings(db: Session, model: str) -> bool:
    """True si existe al menos un embedding indexado para ese modelo."""
    stmt = select(func.count(ChunkEmbedding.id)).where(ChunkEmbedding.model == model)
    return (db.execute(stmt).scalar_one() or 0) > 0


def count_embeddings(db: Session, model: str | None = None) -> int:
    stmt = select(func.count(ChunkEmbedding.id))
    if model:
        stmt = stmt.where(ChunkEmbedding.model == model)
    return db.execute(stmt).scalar_one() or 0


def index_document(
    db: Session, provider: BaseLLMProvider, document_id: int, model: str
) -> int:
    """Genera (o regenera) los embeddings de un documento. Devuelve nº indexados.

    Reemplaza cualquier embedding previo de los chunks (permite cambiar de
    modelo de embeddings sin residuos).
    """
    chunks = list(
        db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        ).scalars()
    )
    if not chunks:
        return 0

    indexed = 0
    for start in range(0, len(chunks), _EMBED_BATCH):
        batch = chunks[start : start + _EMBED_BATCH]
        vectors = provider.embed([c.content for c in batch], model)
        if len(vectors) != len(batch):
            raise LLMProviderError(
                "El proveedor devolvió un número de embeddings distinto al esperado."
            )
        chunk_ids = [c.id for c in batch]
        db.execute(delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(chunk_ids)))
        for chunk, vector in zip(batch, vectors):
            db.add(
                ChunkEmbedding(
                    chunk_id=chunk.id,
                    model=model,
                    dim=len(vector),
                    vector=json.dumps(vector),
                )
            )
            indexed += 1
        db.commit()

    logger.info(
        "Embeddings indexados",
        extra={"extra_data": {"document_id": document_id, "model": model, "chunks": indexed}},
    )
    return indexed


def reindex_all(db: Session, provider: BaseLLMProvider, model: str) -> dict[str, int | str]:
    """Reindexa los embeddings de todos los documentos."""
    document_ids = list(db.execute(select(Document.id)).scalars())
    total = 0
    for document_id in document_ids:
        total += index_document(db, provider, document_id, model)
    return {"documents": len(document_ids), "indexed_chunks": total, "model": model}


def semantic_search(
    db: Session, provider: BaseLLMProvider, query: str, top_k: int, model: str
) -> list["ChunkHit"]:
    """Búsqueda semántica por similitud coseno. Puede lanzar LLMProviderError."""
    from app.rag.retriever import ChunkHit  # import local: evita ciclo

    query_vectors = provider.embed([query], model)
    if not query_vectors:
        return []
    query_vec = query_vectors[0]

    rows = db.execute(
        select(DocumentChunk, Document, ChunkEmbedding)
        .join(Document, DocumentChunk.document_id == Document.id)
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
        .where(ChunkEmbedding.model == model)
    ).all()
    if not rows:
        return []

    scored: list[ChunkHit] = []
    for chunk, document, embedding in rows:
        try:
            vector = json.loads(embedding.vector)
        except (json.JSONDecodeError, TypeError):
            continue
        score = cosine_similarity(query_vec, vector)
        if score <= 0.0:
            continue
        scored.append(
            ChunkHit(
                document_id=document.id,
                filename=document.filename,
                chunk_index=chunk.chunk_index,
                score=round(score, 4),
                snippet=make_snippet(chunk.content, query, 300),
                content=chunk.content,
                method="semantic",
            )
        )
    scored.sort(key=lambda hit: -hit.score)
    return scored[:top_k]
