"""Schemas Pydantic de la API pública.

Separan el contrato HTTP de los modelos ORM internos.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Salud y modelos
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    app_name: str
    app_env: str
    version: str
    database: str
    auth_enabled: bool


class OllamaHealthResponse(BaseModel):
    status: Literal["up", "down"]
    base_url: str
    models_available: int = 0
    default_model: str
    default_model_available: bool = False
    detail: str | None = None


class ModelInfoResponse(BaseModel):
    name: str
    size_bytes: int | None = None
    modified_at: str | None = None
    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None


class ModelTestRequest(BaseModel):
    model: str | None = Field(default=None, description="Modelo a probar; por defecto el configurado")
    prompt: str = Field(default="Responde únicamente: OK", max_length=2000)


class ModelTestResponse(BaseModel):
    ok: bool
    model: str
    latency_ms: int | None = None
    output_snippet: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Agentes y enrutado
# ---------------------------------------------------------------------------


class AgentInfo(BaseModel):
    name: str
    display_name: str
    category: str
    description: str
    allowed_tools: list[str]
    default_model: str | None = None
    output_sections: list[str]
    enabled: bool = True


class AgentCategoriesResponse(BaseModel):
    categories: dict[str, list[str]]


class RouteRequest(BaseModel):
    task: str = Field(min_length=1)


class RouteResponse(BaseModel):
    detected_intent: str
    intent_confidence: float
    classification_method: str
    selected_agent: str
    auxiliary_agents: list[str]
    reason: str
    matched_keywords: list[str] = []


class ExecuteRequest(BaseModel):
    task: str = Field(min_length=1, description="Tarea o instrucción del usuario")
    agent_name: str | None = Field(
        default=None, description="Agente concreto (modo manual); si es null, decide el router"
    )
    model: str | None = Field(default=None, description="Modelo Ollama a usar")
    use_documents: bool = Field(
        default=False, description="Usar documentos subidos como contexto (RAG)"
    )
    extra_context: str | None = Field(
        default=None, description="Contexto adicional opcional (texto pegado)"
    )


class SquadInfo(BaseModel):
    name: str
    display_name: str
    category: str
    description: str
    members: list[str]
    mode: str = "pipeline"


class SquadExecuteRequest(BaseModel):
    task: str = Field(min_length=1, description="Tarea o instrucción para el equipo")
    squad_name: str | None = Field(
        default=None, description="Squad predefinido a usar (si null, se usa agent_names)"
    )
    agent_names: list[str] | None = Field(
        default=None, description="Equipo ad-hoc: lista ordenada de agentes (2-8)"
    )
    model: str | None = Field(default=None, description="Modelo Ollama a usar")
    use_documents: bool = Field(default=False, description="Usar documentos subidos (RAG)")
    extra_context: str | None = Field(default=None, description="Contexto adicional opcional")


class ToolResultSummary(BaseModel):
    tool_name: str
    status: str
    summary: str
    error_message: str | None = None
    duration_ms: int


class VerificationCheckOut(BaseModel):
    name: str
    passed: bool
    detail: str


class VerificationOut(BaseModel):
    passed: bool
    issues: list[str]
    checks: list[VerificationCheckOut]


class ConfidenceOut(BaseModel):
    score: float
    breakdown: dict[str, float]
    notes: list[str]


class ChainOfWorkStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_number: int
    step_type: str
    title: str
    description: str
    agent_name: str | None = None
    tool_name: str | None = None
    tool_input_summary: str | None = None
    tool_output_summary: str | None = None
    evidence: str | None = None
    risk_level: str
    created_at: datetime


class ExecutionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    selected_by_router: bool
    intent: str
    model_provider: str
    model_name: str
    confidence_score: float | None = None
    status: str
    created_at: datetime
    finished_at: datetime | None = None
    error_message: str | None = None


class ExecutionDetail(ExecutionSummary):
    user_input: str
    final_output: str


class ExecutionResponse(BaseModel):
    """Respuesta completa de una ejecución (modo auto o manual)."""

    execution_id: int
    status: str
    agent_name: str
    selected_by_router: bool
    detected_intent: str
    intent_confidence: float | None = None
    auxiliary_agents: list[str] = []
    model_name: str
    final_output: str
    confidence: ConfidenceOut | None = None
    verification: VerificationOut | None = None
    tool_results: list[ToolResultSummary] = []
    documents_used: int = 0
    error_message: str | None = None
    chain_of_work: list[ChainOfWorkStepOut] = []


class ChainOfWorkResponse(BaseModel):
    execution_id: int
    steps: list[ChainOfWorkStepOut]


# ---------------------------------------------------------------------------
# Documentos (RAG)
# ---------------------------------------------------------------------------


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    text_hash: str
    uploaded_at: datetime


class DocumentDetail(DocumentOut):
    chunk_count: int
    preview: str


class DocumentUploadResponse(BaseModel):
    document: DocumentOut
    chunk_count: int
    message: str


class DocumentSearchRequest(BaseModel):
    query: str = Field(min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: Literal["keyword", "semantic", "hybrid"] = Field(
        default="hybrid", description="keyword (sin LLM), semantic (embeddings) o hybrid"
    )


class DocumentSearchHit(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    score: float
    snippet: str
    method: str = "keyword"


class DocumentSearchResponse(BaseModel):
    query: str
    mode: str
    hits: list[DocumentSearchHit]


class EmbeddingIndexResponse(BaseModel):
    documents: int
    indexed_chunks: int
    model: str
    message: str


# ---------------------------------------------------------------------------
# Métricas (dashboard)
# ---------------------------------------------------------------------------


class ToolUsageItem(BaseModel):
    tool_name: str
    count: int
    errors: int


class TimelinePoint(BaseModel):
    date: str
    count: int


class MetricsSummary(BaseModel):
    total_executions: int
    completed: int
    warnings: int
    failed: int
    success_rate: float
    avg_confidence: float | None = None
    by_agent: dict[str, int]
    by_intent: dict[str, int]
    by_status: dict[str, int]
    tool_usage: list[ToolUsageItem]
    timeline: list[TimelinePoint]
    documents: int
    chunks: int
    embeddings: int
    embedding_model: str


# ---------------------------------------------------------------------------
# Herramientas
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Programador de tareas (scheduler)
# ---------------------------------------------------------------------------

TargetKind = Literal["auto", "agent", "squad", "team"]
ScheduleKind = Literal["once", "interval", "daily", "weekly", "cron"]


class ScheduledTaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    task: str = Field(min_length=1, description="Instrucción a ejecutar")
    extra_context: str | None = None
    model: str | None = None
    use_documents: bool = False

    target_kind: TargetKind = "auto"
    target_ref: str | None = Field(default=None, description="Agente o squad según target_kind")
    agent_names: list[str] | None = Field(default=None, description="Equipo ad-hoc (target_kind=team)")

    schedule_kind: ScheduleKind
    run_at: datetime | None = Field(default=None, description="Momento exacto (once), en UTC si no lleva zona")
    interval_minutes: int | None = Field(default=None, ge=1, le=525600)
    time_of_day: str | None = Field(default=None, description="HH:MM para daily/weekly")
    day_of_week: int | None = Field(default=None, ge=0, le=6, description="0=lunes … 6=domingo (weekly)")
    cron: str | None = Field(default=None, description="Expresión cron de 5 campos")
    timezone: str = Field(default="UTC", max_length=64)


class ScheduledTaskUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    task: str | None = None
    extra_context: str | None = None
    model: str | None = None
    use_documents: bool | None = None
    enabled: bool | None = None

    target_kind: TargetKind | None = None
    target_ref: str | None = None
    agent_names: list[str] | None = None

    schedule_kind: ScheduleKind | None = None
    run_at: datetime | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=525600)
    time_of_day: str | None = None
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    cron: str | None = None
    timezone: str | None = Field(default=None, max_length=64)


class ScheduledRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: int | None = None
    status: str
    message: str
    started_at: datetime
    finished_at: datetime | None = None


class ScheduledTaskOut(BaseModel):
    id: int
    name: str
    task: str
    extra_context: str | None = None
    model: str | None = None
    use_documents: bool
    target_kind: str
    target_ref: str
    agent_names: list[str]
    schedule_kind: str
    schedule_human: str
    run_at: datetime | None = None
    interval_minutes: int | None = None
    time_of_day: str | None = None
    day_of_week: int | None = None
    cron: str | None = None
    timezone: str
    enabled: bool
    status: str
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_status: str | None = None
    last_execution_id: int | None = None
    run_count: int
    created_at: datetime


class ScheduledTaskDetail(ScheduledTaskOut):
    runs: list[ScheduledRunOut] = []


class SchedulerStatusResponse(BaseModel):
    enabled: bool
    running: bool
    poll_seconds: int
    total_tasks: int
    active_tasks: int
    next_run_at: datetime | None = None


# ---------------------------------------------------------------------------
# Herramientas
# ---------------------------------------------------------------------------


class ToolInfo(BaseModel):
    name: str
    category: str
    description: str
    required_role: str
    timeout_seconds: int
    input_schema: dict[str, Any]


class ToolCategoriesResponse(BaseModel):
    categories: dict[str, list[str]]


class ErrorResponse(BaseModel):
    detail: str
