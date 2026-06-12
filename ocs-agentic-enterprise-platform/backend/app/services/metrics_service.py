"""Servicio de métricas (Fase 2): agregados para el dashboard."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AgentExecution, ChunkEmbedding, Document, DocumentChunk, ToolLog


def _counts_by(db: Session, column) -> dict[str, int]:
    rows = db.execute(select(column, func.count()).group_by(column)).all()
    return {str(value): int(count) for value, count in rows}


def build_summary(db: Session, timeline_days: int = 14) -> dict:
    """Construye el resumen de métricas para el panel."""
    total = db.execute(select(func.count(AgentExecution.id))).scalar_one() or 0
    by_status = _counts_by(db, AgentExecution.status)
    by_agent = _counts_by(db, AgentExecution.agent_name)
    by_intent = _counts_by(db, AgentExecution.intent)

    completed = by_status.get("completed", 0)
    warnings = by_status.get("completed_with_warnings", 0)
    failed = by_status.get("failed", 0)
    success_rate = round(100 * (completed + warnings) / total, 1) if total else 0.0

    avg_conf = db.execute(
        select(func.avg(AgentExecution.confidence_score)).where(
            AgentExecution.confidence_score.isnot(None)
        )
    ).scalar_one()
    avg_confidence = round(float(avg_conf), 3) if avg_conf is not None else None

    # Uso de herramientas (total y errores) por nombre.
    tool_rows = db.execute(
        select(
            ToolLog.tool_name,
            func.count(),
            func.sum(case((ToolLog.status != "success", 1), else_=0)),
        ).group_by(ToolLog.tool_name)
    ).all()
    tool_usage = [
        {"tool_name": name, "count": int(count), "errors": int(errors or 0)}
        for name, count, errors in sorted(tool_rows, key=lambda r: -int(r[1]))
    ]

    # Línea temporal de ejecuciones por día (últimos N días).
    since = datetime.now(timezone.utc) - timedelta(days=timeline_days)
    timeline_rows = db.execute(
        select(func.date(AgentExecution.created_at), func.count())
        .where(AgentExecution.created_at >= since)
        .group_by(func.date(AgentExecution.created_at))
    ).all()
    timeline_map = {str(day): int(count) for day, count in timeline_rows}
    timeline: list[dict[str, object]] = []
    for offset in range(timeline_days - 1, -1, -1):
        day = (datetime.now(timezone.utc) - timedelta(days=offset)).date().isoformat()
        timeline.append({"date": day, "count": timeline_map.get(day, 0)})

    settings = get_settings()
    documents = db.execute(select(func.count(Document.id))).scalar_one() or 0
    chunks = db.execute(select(func.count(DocumentChunk.id))).scalar_one() or 0
    embeddings = db.execute(select(func.count(ChunkEmbedding.id))).scalar_one() or 0

    return {
        "total_executions": total,
        "completed": completed,
        "warnings": warnings,
        "failed": failed,
        "success_rate": success_rate,
        "avg_confidence": avg_confidence,
        "by_agent": by_agent,
        "by_intent": by_intent,
        "by_status": by_status,
        "tool_usage": tool_usage,
        "timeline": timeline,
        "documents": documents,
        "chunks": chunks,
        "embeddings": embeddings,
        "embedding_model": settings.ollama_embed_model,
    }
