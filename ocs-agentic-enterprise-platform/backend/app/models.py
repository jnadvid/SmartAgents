"""Modelos ORM (SQLAlchemy 2.0) de la plataforma.

Todas las tablas viven en SQLite local. Los campos de texto largos se
guardan ya saneados/truncados por la capa de auditoría.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(50), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Agent(Base):
    """Espejo persistente del registro de agentes (para auditoría y gestión)."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(100), index=True)
    selected_by_router: Mapped[bool] = mapped_column(Boolean, default=True)
    intent: Mapped[str] = mapped_column(String(100), default="", index=True)
    model_provider: Mapped[str] = mapped_column(String(50), default="ollama")
    model_name: Mapped[str] = mapped_column(String(100), default="")
    user_input: Mapped[str] = mapped_column(Text, default="")
    final_output: Mapped[str] = mapped_column(Text, default="")
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["ChainOfWorkStep"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan", order_by="ChainOfWorkStep.step_number"
    )
    tool_logs: Mapped[list["ToolLog"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan"
    )
    route: Mapped["TaskRoute | None"] = relationship(
        back_populates="execution", cascade="all, delete-orphan", uselist=False
    )


class ChainOfWorkStep(Base):
    """Paso auditable del Chain-of-Work.

    Registra decisiones, evidencias y resultados; nunca el razonamiento
    literal (chain-of-thought) del modelo.
    """

    __tablename__ = "chain_of_work_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="CASCADE"), index=True
    )
    step_number: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="info")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    execution: Mapped[AgentExecution] = relationship(back_populates="steps")


class ToolLog(Base):
    __tablename__ = "tool_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="CASCADE"), index=True
    )
    agent_name: Mapped[str] = mapped_column(String(100))
    tool_name: Mapped[str] = mapped_column(String(100), index=True)
    input_summary: Mapped[str] = mapped_column(Text, default="")
    output_summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    execution: Mapped[AgentExecution] = relationship(back_populates="tool_logs")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), index=True)
    path: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(100), default="text/plain")
    text_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentChunk.chunk_index"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[Document] = relationship(back_populates="chunks")


class TaskRoute(Base):
    __tablename__ = "task_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="CASCADE"), index=True
    )
    user_input_summary: Mapped[str] = mapped_column(Text, default="")
    detected_intent: Mapped[str] = mapped_column(String(100), index=True)
    selected_agent: Mapped[str] = mapped_column(String(100))
    auxiliary_agents: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    execution: Mapped[AgentExecution] = relationship(back_populates="route")
