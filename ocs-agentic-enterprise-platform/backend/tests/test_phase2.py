"""Tests de la Fase 2: RAG semántico (embeddings), métricas y exportación."""
from __future__ import annotations

import pytest

from app.llm.base import GenerationResult
from app.models import Document, DocumentChunk
from app.orchestration.execution_engine import ExecutionEngine
from app.rag import embeddings as emb
from app.rag.retriever import retrieve_relevant
from app.services import export_service, metrics_service
from tests.conftest import FakeLLMProvider


class LetterEmbedProvider(FakeLLMProvider):
    """Proveedor de embeddings determinista: vector = recuento de a,b,c,d,e."""

    name = "letters"

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            vectors.append([float(lowered.count(ch)) for ch in "abcde"])
        return vectors


def _seed_document(session_factory) -> int:
    with session_factory() as db:
        document = Document(filename="doc.txt", path="x", content_type="text/plain", text_hash="hh")
        db.add(document)
        db.flush()
        db.add_all(
            [
                DocumentChunk(document_id=document.id, chunk_index=0, content="aaaa aaaa aaaa copia"),
                DocumentChunk(document_id=document.id, chunk_index=1, content="bbbb cccc dddd seguridad"),
            ]
        )
        db.commit()
        return document.id


# ---------------------------------------------------------------------------
# Embeddings / RAG semántico
# ---------------------------------------------------------------------------


def test_cosine_similarity_basic() -> None:
    assert emb.cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
    assert emb.cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert emb.cosine_similarity([1, 1], []) == 0.0  # vector vacío


def test_index_and_semantic_search(memory_session_factory) -> None:
    document_id = _seed_document(memory_session_factory)
    provider = LetterEmbedProvider()

    with memory_session_factory() as db:
        indexed = emb.index_document(db, provider, document_id, "letters")
        assert indexed == 2
        assert emb.has_embeddings(db, "letters") is True

    with memory_session_factory() as db:
        hits = emb.semantic_search(db, provider, "aaaaa", top_k=2, model="letters")
        assert hits, "esperaba resultados semánticos"
        assert hits[0].chunk_index == 0  # el chunk con muchas 'a'
        assert hits[0].method == "semantic"
        assert 0.0 < hits[0].score <= 1.0


def test_retrieve_relevant_falls_back_to_keyword_without_embeddings(memory_session_factory) -> None:
    _seed_document(memory_session_factory)
    with memory_session_factory() as db:
        hits = retrieve_relevant(db, "seguridad", top_k=5, use_embeddings=False)
    assert hits and hits[0].method == "keyword"


def test_retrieve_relevant_hybrid(memory_session_factory) -> None:
    document_id = _seed_document(memory_session_factory)
    provider = LetterEmbedProvider()
    with memory_session_factory() as db:
        emb.index_document(db, provider, document_id, "letters")
    with memory_session_factory() as db:
        hits = retrieve_relevant(
            db, "seguridad", top_k=5, provider=provider, embed_model="letters", use_embeddings=True
        )
    assert hits
    assert all(0.0 <= h.score <= 1.0 for h in hits)


# ---------------------------------------------------------------------------
# Métricas y exportación (sobre ejecuciones reales del motor)
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine(db_session, fake_llm, tool_registry, agent_registry, memory_session_factory) -> ExecutionEngine:
    return ExecutionEngine(
        db=db_session,
        llm=fake_llm,
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        session_factory=memory_session_factory,
    )


def test_metrics_summary(engine, db_session) -> None:
    engine.run(task="Hazme una propuesta comercial para una empresa de logística", model="fake-model")
    engine.run(task="Analiza esta alerta Wazuh de fuerza bruta", model="fake-model")

    summary = metrics_service.build_summary(db_session)
    assert summary["total_executions"] == 2
    assert summary["by_agent"].get("sales_proposal") == 1
    assert summary["by_agent"].get("cyber_threat_analyst") == 1
    assert 0.0 <= summary["success_rate"] <= 100.0
    assert summary["avg_confidence"] is not None
    assert any(t["tool_name"] == "create_sales_proposal" for t in summary["tool_usage"])
    assert len(summary["timeline"]) == 14


def test_export_markdown_and_html(engine, db_session) -> None:
    result = engine.run(task="Genera un informe ejecutivo de prueba", model="fake-model")
    execution = result.execution

    markdown = export_service.build_markdown(db_session, execution)
    assert markdown.startswith(f"# Informe de ejecución #{execution.id}")
    assert "Chain-of-Work" in markdown
    assert execution.agent_name in markdown

    html = export_service.build_html(db_session, execution)
    assert "<html" in html.lower()
    assert f"#{execution.id}" in html
