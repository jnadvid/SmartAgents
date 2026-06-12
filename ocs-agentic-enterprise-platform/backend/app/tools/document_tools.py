"""Herramientas documentales: resumen, acciones, búsqueda y comparación.

Las herramientas que acceden a documentos lo hacen exclusivamente a través
de la base de datos local (chunks ya extraídos), nunca leyendo rutas
arbitrarias del sistema de archivos.
"""
from __future__ import annotations

import difflib
from typing import Any

from pydantic import BaseModel, Field

from app.tools._text_utils import (
    extractive_summary,
    split_sentences,
    text_stats,
    top_keywords,
    tokenize,
)
from app.tools.base import BaseTool, ToolContext, ToolError


def _load_document_text(ctx: ToolContext, document_id: int) -> tuple[str, str]:
    """Devuelve (filename, texto completo) de un documento desde SQLite."""
    if ctx.db_session_factory is None:
        raise ToolError("Esta herramienta requiere acceso a la base de datos local.")
    from app.models import Document  # import local para evitar ciclos

    with ctx.db_session_factory() as db:
        document = db.get(Document, document_id)
        if document is None:
            raise ToolError(f"Documento con id={document_id} no encontrado.")
        text = "\n\n".join(chunk.content for chunk in document.chunks)
        return document.filename, text


# ---------------------------------------------------------------------------
# 1. summarize_text
# ---------------------------------------------------------------------------


class SummarizeTextInput(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    max_sentences: int = Field(default=5, ge=1, le=15)


class SummarizeTextTool(BaseTool):
    name = "summarize_text"
    category = "documents"
    description = (
        "Resumen extractivo determinista de un texto: frases clave literales, "
        "palabras clave y métricas. No genera contenido nuevo."
    )
    input_schema = SummarizeTextInput
    timeout_seconds = 10

    def execute(self, payload: SummarizeTextInput, ctx: ToolContext) -> dict[str, Any]:
        return {
            "stats": text_stats(payload.text),
            "key_sentences": extractive_summary(payload.text, payload.max_sentences),
            "keywords": [{"term": term, "count": count} for term, count in top_keywords(payload.text, 10)],
        }


# ---------------------------------------------------------------------------
# 2. extract_action_items
# ---------------------------------------------------------------------------


class ExtractActionItemsInput(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    max_items: int = Field(default=20, ge=1, le=50)


_ACTION_MARKERS = (
    "todo", "pendiente", "accion:", "acción:", "hay que", "debemos", "necesitamos",
    "tenemos que", "se debe", "debera", "deberá", "action:", "next step", "[ ]", "- [ ]",
)
_IMPERATIVE_STARTS = (
    "revisar", "enviar", "preparar", "crear", "llamar", "actualizar", "definir",
    "documentar", "validar", "confirmar", "agendar", "planificar", "contactar",
    "review", "send", "prepare", "create", "update", "schedule", "confirm",
)


class ExtractActionItemsTool(BaseTool):
    name = "extract_action_items"
    category = "documents"
    description = (
        "Detecta acciones pendientes en un texto (marcadores TODO, frases "
        "imperativas, casillas) y las lista con su línea de origen."
    )
    input_schema = ExtractActionItemsInput
    timeout_seconds = 10

    def execute(self, payload: ExtractActionItemsInput, ctx: ToolContext) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for line_number, raw_line in enumerate(payload.text.splitlines(), start=1):
            line = raw_line.strip()
            if not line or len(line) < 4:
                continue
            lowered = line.lower()
            marker_hit = any(marker in lowered for marker in _ACTION_MARKERS)
            stripped = lowered.lstrip("-*•0123456789. ")
            imperative_hit = stripped.startswith(_IMPERATIVE_STARTS)
            if not (marker_hit or imperative_hit):
                continue
            normalized = stripped[:120]
            if normalized in seen:
                continue
            seen.add(normalized)
            items.append({"line": line_number, "item": line[:300]})
            if len(items) >= payload.max_items:
                break
        return {"action_items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# 3. search_documents
# ---------------------------------------------------------------------------


class SearchDocumentsInput(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchDocumentsTool(BaseTool):
    name = "search_documents"
    category = "documents"
    description = (
        "Busca por palabras clave en los documentos subidos (chunks en SQLite) "
        "y devuelve citas con documento, chunk y fragmento."
    )
    input_schema = SearchDocumentsInput
    timeout_seconds = 15

    def execute(self, payload: SearchDocumentsInput, ctx: ToolContext) -> dict[str, Any]:
        if ctx.db_session_factory is None:
            raise ToolError("Esta herramienta requiere acceso a la base de datos local.")
        from app.rag.retriever import search_chunks

        with ctx.db_session_factory() as db:
            hits = search_chunks(db, payload.query, payload.top_k)
        return {
            "query": payload.query,
            "hits": [
                {
                    "document_id": hit.document_id,
                    "filename": hit.filename,
                    "chunk_index": hit.chunk_index,
                    "score": round(hit.score, 3),
                    "snippet": hit.snippet,
                }
                for hit in hits
            ],
            "count": len(hits),
        }


# ---------------------------------------------------------------------------
# 4. summarize_document
# ---------------------------------------------------------------------------


class SummarizeDocumentInput(BaseModel):
    document_id: int = Field(ge=1)
    max_sentences: int = Field(default=6, ge=1, le=15)


class SummarizeDocumentTool(BaseTool):
    name = "summarize_document"
    category = "documents"
    description = "Resumen extractivo de un documento subido (por id), con métricas y keywords."
    input_schema = SummarizeDocumentInput
    timeout_seconds = 15

    def execute(self, payload: SummarizeDocumentInput, ctx: ToolContext) -> dict[str, Any]:
        filename, text = _load_document_text(ctx, payload.document_id)
        return {
            "document_id": payload.document_id,
            "filename": filename,
            "stats": text_stats(text),
            "key_sentences": extractive_summary(text, payload.max_sentences),
            "keywords": [{"term": term, "count": count} for term, count in top_keywords(text, 10)],
        }


# ---------------------------------------------------------------------------
# 5. compare_documents
# ---------------------------------------------------------------------------


class CompareDocumentsInput(BaseModel):
    document_id_a: int = Field(ge=1)
    document_id_b: int = Field(ge=1)


class CompareDocumentsTool(BaseTool):
    name = "compare_documents"
    category = "documents"
    description = (
        "Compara dos documentos subidos: similitud aproximada, keywords comunes "
        "y exclusivas, y diferencia de tamaño."
    )
    input_schema = CompareDocumentsInput
    timeout_seconds = 20

    def execute(self, payload: CompareDocumentsInput, ctx: ToolContext) -> dict[str, Any]:
        name_a, text_a = _load_document_text(ctx, payload.document_id_a)
        name_b, text_b = _load_document_text(ctx, payload.document_id_b)

        # La similitud se calcula sobre un prefijo acotado: suficiente como
        # indicador y evita costes cuadráticos en documentos grandes.
        sample_a, sample_b = text_a[:20000], text_b[:20000]
        similarity = difflib.SequenceMatcher(None, sample_a, sample_b).ratio()

        tokens_a, tokens_b = set(tokenize(text_a)), set(tokenize(text_b))
        common = sorted(tokens_a & tokens_b)
        only_a = sorted(tokens_a - tokens_b)
        only_b = sorted(tokens_b - tokens_a)

        return {
            "document_a": {"id": payload.document_id_a, "filename": name_a, "stats": text_stats(text_a)},
            "document_b": {"id": payload.document_id_b, "filename": name_b, "stats": text_stats(text_b)},
            "similarity_ratio": round(similarity, 3),
            "similarity_note": "Similitud aproximada sobre los primeros 20k caracteres.",
            "common_keywords": common[:25],
            "only_in_a": only_a[:25],
            "only_in_b": only_b[:25],
            "sentences_a": len(split_sentences(text_a)),
            "sentences_b": len(split_sentences(text_b)),
        }
