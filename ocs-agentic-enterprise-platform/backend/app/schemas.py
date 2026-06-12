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


class DocumentSearchHit(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    score: float
    snippet: str


class DocumentSearchResponse(BaseModel):
    query: str
    hits: list[DocumentSearchHit]


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
