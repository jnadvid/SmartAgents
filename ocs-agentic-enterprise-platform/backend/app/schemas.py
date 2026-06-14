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
    data_access: list[str] = []
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

    connector: str | None = Field(default=None, description="Conector de datos a leer antes de ejecutar")
    connector_params: dict[str, Any] | None = Field(default=None, description="Parámetros del conector")

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

    connector: str | None = None
    connector_params: dict[str, Any] | None = None

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
    connector: str | None = None
    connector_params: dict[str, Any] = {}
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
# Conectores de datos
# ---------------------------------------------------------------------------


class ConnectorInfo(BaseModel):
    name: str
    display_name: str
    category: str
    description: str
    requires_network: bool
    enabled: bool
    input_schema: dict[str, Any]


class ConnectorCategoriesResponse(BaseModel):
    categories: dict[str, list[str]]


class ConnectorReadRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    max_records: int = Field(default=20, ge=1, le=200, description="Máximo de registros a devolver en la vista previa")


class ConnectorReadResponse(BaseModel):
    connector: str
    status: str
    count: int
    summary: str = ""
    source: str = ""
    records: list[dict[str, Any]] = []
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Ajustes editables (runtime)
# ---------------------------------------------------------------------------


class SettingsOut(BaseModel):
    default_ollama_model: str
    enable_pentest_tools: bool
    pentest_scope_allowlist: str
    pentest_execution_mode: str
    pentest_wsl_distro: str
    pentest_wsl_user: str
    pentest_wsl_password_set: bool = False
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_from: str
    smtp_use_tls: bool
    smtp_password_set: bool = False
    notify_email: str
    company_name: str = ""
    report_logo_url: str = ""
    report_footer: str = ""
    host_os: str
    wsl_available: bool
    email_configured: bool = False
    available_models: list[str] = []


class SettingsUpdate(BaseModel):
    default_ollama_model: str | None = None
    enable_pentest_tools: bool | None = None
    pentest_scope_allowlist: str | None = None
    pentest_execution_mode: Literal["auto", "native", "wsl"] | None = None
    pentest_wsl_distro: str | None = None
    pentest_wsl_user: str | None = None
    pentest_wsl_password: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool | None = None
    notify_email: str | None = None
    company_name: str | None = None
    report_logo_url: str | None = None
    report_footer: str | None = None


class EmailTestRequest(BaseModel):
    to: str = Field(min_length=3, description="Destinatario de la prueba")


# ---------------------------------------------------------------------------
# Pentesting (herramientas de Kali, autorizado)
# ---------------------------------------------------------------------------


class PentestToolInfo(BaseModel):
    name: str
    display_name: str
    category: str
    description: str
    binary: str
    intrusive: bool
    available: bool


class PentestStatusResponse(BaseModel):
    enabled: bool
    scope_configured: bool
    scope_count: int
    execution_mode: str = "native"
    wsl_distro: str = "kali-linux"
    wordlists: list[str] = []
    profiles: dict[str, list[str]]
    tools: list[PentestToolInfo]


class PentestRunRequest(BaseModel):
    target: str = Field(min_length=1, max_length=2000, description="URL o host AUTORIZADO a escanear")
    authorized: bool = Field(default=False, description="Confirmas tener autorización para el objetivo")
    profile: Literal["recon", "web", "full"] = "recon"
    tools: list[str] | None = Field(default=None, description="Herramientas concretas (anula el perfil)")
    options: dict[str, Any] = Field(default_factory=dict, description="Opciones por herramienta (ports, wordlist…)")
    agent_name: str = Field(default="web_pentester", description="Agente de ciberseguridad que analiza")
    model: str | None = None
    email_to: str | None = Field(default=None, description="Si se indica, envía el informe a este email")


class PentestAutoRequest(BaseModel):
    target: str = Field(min_length=1, max_length=2000, description="URL o host AUTORIZADO")
    authorized: bool = Field(default=False, description="Confirmas tener autorización para el objetivo")
    aggressive: bool = Field(default=False, description="Incluye fases activas (NSE vuln, sqlmap)")
    options: dict[str, Any] = Field(default_factory=dict)
    agent_name: str = Field(default="pentest_lead", description="Agente de ciberseguridad que redacta el informe")
    model: str | None = None
    email_to: str | None = Field(default=None, description="Si se indica, envía el informe a este email")


class PentestToolResultOut(BaseModel):
    tool_name: str
    status: str
    phase: str = ""
    summary: str = ""
    command: str = ""
    returncode: int | None = None
    duration_ms: int = 0
    output: str = ""


class FindingOut(BaseModel):
    tool: str
    severity: str
    title: str
    cve: str = ""
    score: float = 0.0


class InstallStatusResponse(BaseModel):
    running: bool
    returncode: int | None = None
    started_at: float | None = None
    finished_at: float | None = None
    mode: str = ""
    log: str = ""


class PentestRunResponse(BaseModel):
    target: str
    host: str
    status: str
    message: str
    profile: str = ""
    tools: list[PentestToolResultOut] = []
    findings: list[FindingOut] = []
    findings_by_severity: dict[str, int] = {}
    max_severity: str = "info"
    execution: ExecutionResponse | None = None
    emailed: bool = False
    email_message: str | None = None


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
