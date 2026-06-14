"""AgentRunner: fachada de alto nivel para ejecutar tareas con agentes.

Mantiene los singletons de proceso (proveedor LLM, registros de agentes y
herramientas) y traduce resultados del motor a schemas de la API.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from sqlalchemy.orm import Session

from app.agents.registry import AgentRegistry, build_default_registry as build_agents
from app.agents.squads import SquadRegistry, build_default_squad_registry
from app.connectors.registry import ConnectorRegistry, build_default_connector_registry
from app.config import get_settings
from app.pentest.registry import PentestRegistry, build_default_pentest_registry
from app.llm.base import BaseLLMProvider
from app.llm.ollama_provider import OllamaProvider
from app.orchestration.execution_engine import EngineResult, ExecutionEngine
from app.orchestration.task_router import TaskRouter
from app.schemas import (
    ChainOfWorkStepOut,
    ConfidenceOut,
    ExecuteRequest,
    ExecutionResponse,
    RouteResponse,
    SquadExecuteRequest,
    SquadInfo,
    ToolResultSummary,
    VerificationCheckOut,
    VerificationOut,
)
from app.tools.registry import ToolRegistry, build_default_registry as build_tools

logger = logging.getLogger(__name__)


@lru_cache
def get_llm_provider() -> BaseLLMProvider:
    settings = get_settings()
    return OllamaProvider(base_url=settings.ollama_base_url, timeout=settings.ollama_timeout)


@lru_cache
def get_tool_registry() -> ToolRegistry:
    return build_tools()


@lru_cache
def get_agent_registry() -> AgentRegistry:
    return build_agents()


@lru_cache
def get_squad_registry() -> SquadRegistry:
    return build_default_squad_registry()


@lru_cache
def get_connector_registry() -> ConnectorRegistry:
    return build_default_connector_registry()


@lru_cache
def get_pentest_registry() -> PentestRegistry:
    return build_default_pentest_registry()


def reset_runtime_singletons() -> None:
    """Limpia los singletons (útil en tests)."""
    get_llm_provider.cache_clear()
    get_tool_registry.cache_clear()
    get_agent_registry.cache_clear()
    get_squad_registry.cache_clear()
    get_connector_registry.cache_clear()
    get_pentest_registry.cache_clear()


class AgentRunner:
    """Caso de uso principal: enrutar y ejecutar tareas."""

    def __init__(
        self,
        db: Session,
        llm: BaseLLMProvider | None = None,
        tool_registry: ToolRegistry | None = None,
        agent_registry: AgentRegistry | None = None,
        session_factory=None,
    ) -> None:
        self.db = db
        self.llm = llm or get_llm_provider()
        self.tool_registry = tool_registry or get_tool_registry()
        self.agent_registry = agent_registry or get_agent_registry()
        self.engine = ExecutionEngine(
            db=db,
            llm=self.llm,
            tool_registry=self.tool_registry,
            agent_registry=self.agent_registry,
            session_factory=session_factory,
        )

    # ------------------------------------------------------------------

    def preview_route(self, task: str) -> RouteResponse:
        """Clasifica y enruta SIN ejecutar (vista previa para el frontend)."""
        settings = get_settings()
        router = TaskRouter(self.agent_registry)
        decision = router.route(
            task,
            llm=self.llm if settings.use_llm_intent_fallback else None,
            model=settings.default_ollama_model,
            use_llm_fallback=settings.use_llm_intent_fallback,
        )
        return RouteResponse(
            detected_intent=decision.detected_intent,
            intent_confidence=decision.intent_confidence,
            classification_method=decision.classification_method,
            selected_agent=decision.selected_agent,
            auxiliary_agents=decision.auxiliary_agents,
            reason=decision.reason,
            matched_keywords=decision.matched_keywords,
        )

    def execute(self, request: ExecuteRequest, username: str = "local") -> ExecutionResponse:
        """Ejecuta la tarea (modo auto si agent_name es None) y arma la respuesta."""
        result = self.engine.run(
            task=request.task,
            agent_name=request.agent_name,
            model=request.model,
            use_documents=request.use_documents,
            extra_context=request.extra_context,
            username=username,
        )
        return self._to_response(result)

    # ------------------------------------------------------------------
    # Multi-agente (squads)
    # ------------------------------------------------------------------

    def list_squads(self) -> list[SquadInfo]:
        """Catálogo de equipos predefinidos."""
        return [SquadInfo(**squad.describe()) for squad in get_squad_registry().list_squads()]

    def execute_squad(self, request: SquadExecuteRequest, username: str = "local") -> ExecutionResponse:
        """Ejecuta un equipo (predefinido o ad-hoc) sobre una tarea."""
        squad_label, squad_display, members = self._resolve_squad(request)
        result = self.engine.run_squad(
            task=request.task,
            members=members,
            squad_label=squad_label,
            squad_display=squad_display,
            model=request.model,
            use_documents=request.use_documents,
            extra_context=request.extra_context,
            username=username,
        )
        return self._to_response(result)

    @staticmethod
    def _resolve_squad(request: SquadExecuteRequest) -> tuple[str, str, list[str]]:
        """Resuelve el equipo a ejecutar: predefinido (squad_name) o ad-hoc (agent_names)."""
        if request.squad_name:
            squad = get_squad_registry().get(request.squad_name)
            if squad is None:
                available = ", ".join(get_squad_registry().names())
                raise ValueError(
                    f"Equipo desconocido: '{request.squad_name}'. Disponibles: {available}."
                )
            return f"squad:{squad.name}", squad.display_name, list(squad.members)
        if request.agent_names:
            members = [name for name in request.agent_names if name]
            if len(members) < 2:
                raise ValueError("Un equipo ad-hoc requiere al menos 2 agentes.")
            return "squad:custom", "Equipo personalizado", members
        raise ValueError("Indica 'squad_name' o 'agent_names' para ejecutar un equipo.")

    # ------------------------------------------------------------------

    @staticmethod
    def _to_response(result: EngineResult) -> ExecutionResponse:
        execution = result.execution
        verification = None
        if result.verification is not None:
            verification = VerificationOut(
                passed=result.verification.passed,
                issues=result.verification.issues,
                checks=[
                    VerificationCheckOut(name=c.name, passed=c.passed, detail=c.detail)
                    for c in result.verification.checks
                ],
            )
        confidence = None
        if result.confidence is not None:
            confidence = ConfidenceOut(
                score=result.confidence.score,
                breakdown=result.confidence.breakdown,
                notes=result.confidence.notes,
            )
        return ExecutionResponse(
            execution_id=execution.id,
            status=execution.status,
            agent_name=execution.agent_name,
            selected_by_router=execution.selected_by_router,
            detected_intent=execution.intent,
            intent_confidence=result.route.intent_confidence,
            auxiliary_agents=result.route.auxiliary_agents,
            model_name=execution.model_name,
            final_output=execution.final_output or "",
            confidence=confidence,
            verification=verification,
            tool_results=[
                ToolResultSummary(
                    tool_name=tr.tool_name,
                    status=tr.status,
                    summary=tr.summary,
                    error_message=tr.error_message,
                    duration_ms=tr.duration_ms,
                )
                for tr in result.tool_results
            ],
            documents_used=result.documents_used,
            error_message=execution.error_message,
            chain_of_work=[ChainOfWorkStepOut.model_validate(step) for step in result.steps],
        )
