"""Tests de las herramientas generales (deterministas, sin red)."""
from __future__ import annotations

from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry


def run(tool_registry: ToolRegistry, name: str, payload: dict, ctx: ToolContext | None = None):
    result = tool_registry.run_tool(name, payload, ctx)
    assert result.status == "success", f"{name} falló: {result.error_message}"
    return result.output


def test_summarize_text(tool_registry: ToolRegistry) -> None:
    text = (
        "La empresa creció un 20% el último año. El equipo de ventas cerró 40 contratos. "
        "El churn bajó al 3%. La empresa quiere abrir mercado en Portugal. "
        "El presupuesto de marketing se mantiene estable."
    )
    output = run(tool_registry, "summarize_text", {"text": text, "max_sentences": 2})
    assert output["stats"]["words"] > 20
    assert len(output["key_sentences"]) == 2
    assert any(k["term"] == "empresa" for k in output["keywords"])


def test_extract_action_items(tool_registry: ToolRegistry) -> None:
    text = """Notas de la reunión:
- [ ] Enviar la propuesta al cliente
Hay que revisar el contrato antes del viernes.
TODO: actualizar el CRM
El tiempo fue agradable."""
    output = run(tool_registry, "extract_action_items", {"text": text})
    assert output["count"] >= 3
    items = " | ".join(i["item"] for i in output["action_items"])
    assert "propuesta" in items and "CRM" in items


def test_analyze_table_text_detects_stats_and_outliers(tool_registry: ToolRegistry) -> None:
    csv_text = """mes,ventas,region
enero,100,norte
febrero,110,norte
marzo,95,sur
abril,105,sur
mayo,990,norte
junio,102,sur"""
    output = run(tool_registry, "analyze_table_text", {"text": csv_text})
    assert output["row_count"] == 6
    ventas = next(c for c in output["columns"] if c["name"] == "ventas")
    assert ventas["type"] == "numeric"
    assert ventas["stats"]["max"] == 990
    assert any(a["column"] == "ventas" for a in output["anomalies"])
    region = next(c for c in output["columns"] if c["name"] == "region")
    assert region["type"] == "categorical"


def test_calculate_basic_financials_from_text(tool_registry: ToolRegistry) -> None:
    text = "Ingresos: 120000 euros. Costes fijos: 40000. Costes variables: 30000."
    output = run(tool_registry, "calculate_basic_financials", {"text": text})
    assert output["inputs_used"]["revenue"] == 120000
    assert output["results"]["gross_margin"] == 50000
    assert output["results"]["margin_pct"] == 41.67
    assert "disclaimer" in output


def test_calculate_basic_financials_reports_missing_data(tool_registry: ToolRegistry) -> None:
    output = run(tool_registry, "calculate_basic_financials", {"text": "sin cifras aquí"})
    assert output["missing_data"]


def test_review_contract_text(tool_registry: ToolRegistry) -> None:
    contract = """CLÁUSULA 1. Objeto del contrato.
El proveedor deberá entregar el servicio en 30 días.
CLÁUSULA 2. Penalización: el retraso conlleva una penalización del 5% semanal.
El contrato se renovará automáticamente cada año salvo preaviso de 60 días.
Las partes actuarán con esfuerzos comerciales razonables."""
    output = run(tool_registry, "review_contract_text", {"text": contract})
    risk_ids = {r["risk"] for r in output["risk_hits"]}
    assert "penalizacion" in risk_ids
    assert "renovacion_automatica" in risk_ids
    assert output["obligations"]
    assert output["ambiguities"]
    assert output["clause_count"] >= 2


def test_classify_customer_request(tool_registry: ToolRegistry) -> None:
    text = "Estoy muy molesto: me han hecho un cobro duplicado en la factura y es urgente resolverlo."
    output = run(tool_registry, "classify_customer_request", {"text": text})
    assert output["category"] in ("facturacion", "reclamacion")
    assert output["urgency"] == "alta"
    assert output["tone"] == "negativo"


def test_create_project_plan(tool_registry: ToolRegistry) -> None:
    output = run(
        tool_registry,
        "create_project_plan",
        {"objective": "Implantar un SIEM local con Wazuh", "duration_weeks": 12},
    )
    assert len(output["phases"]) == 4
    assert output["phases"][-1]["end_week"] == 12
    assert output["milestones"][-1]["week"] == 12


def test_create_sales_proposal_reports_missing_fields(tool_registry: ToolRegistry) -> None:
    output = run(tool_registry, "create_sales_proposal", {"need": "Necesitan auditoría de seguridad anual"})
    assert "client" in output["missing_fields"]
    assert any(s["title"] == "Próximos pasos" for s in output["sections"])


def test_generate_markdown_report(tool_registry: ToolRegistry) -> None:
    output = run(
        tool_registry,
        "generate_markdown_report",
        {
            "title": "Informe de prueba",
            "sections": [{"heading": "Contexto", "content": "Todo bien."}],
            "include_toc": True,
        },
    )
    assert output["markdown"].startswith("# Informe de prueba")
    assert "## Contexto" in output["markdown"]


def test_extract_risks_levels(tool_registry: ToolRegistry) -> None:
    text = (
        "Existe riesgo de retraso en la entrega. "
        "Un incumplimiento del contrato implicaría una multa importante. "
        "Queda pendiente definir el alcance."
    )
    output = run(tool_registry, "extract_risks", {"text": text})
    assert output["count"] >= 2
    assert output["by_level"]["high"] >= 1


def test_document_tools_require_db(tool_registry: ToolRegistry) -> None:
    result = tool_registry.run_tool("summarize_document", {"document_id": 1}, ToolContext())
    assert result.status == "error"
    assert "base de datos" in (result.error_message or "").lower()


def test_search_documents_with_db(tool_registry: ToolRegistry, memory_session_factory) -> None:
    from app.models import Document, DocumentChunk

    with memory_session_factory() as session:
        document = Document(filename="politica.txt", path="x", content_type="text/plain", text_hash="h1")
        session.add(document)
        session.flush()
        session.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                content="La política de copias de seguridad exige backup diario cifrado.",
            )
        )
        session.commit()

    ctx = ToolContext(db_session_factory=memory_session_factory)
    output = run(tool_registry, "search_documents", {"query": "copias de seguridad"}, ctx)
    assert output["count"] == 1
    assert output["hits"][0]["filename"] == "politica.txt"
