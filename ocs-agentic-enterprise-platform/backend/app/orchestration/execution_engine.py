"""ExecutionEngine: orquesta la ejecución completa de una tarea.

Flujo: validar entrada -> enrutar -> crear ejecución -> plan -> RAG opcional
-> agente principal (herramientas + Ollama) -> verificación -> agentes
auxiliares (opcional) -> confianza -> persistencia. Todo queda registrado
en el Chain-of-Work.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.agents.registry import AgentRegistry
from app.audit.chain_of_work import ChainOfWorkRecorder
from app.config import get_settings
from app.llm.base import BaseLLMProvider, LLMProviderError
from app.llm.model_router import ModelRouter
from app.models import AgentExecution, ChainOfWorkStep, TaskRoute
from app.orchestration.agent_planner import AgentPlanner
from app.orchestration.confidence_scorer import ConfidenceReport, ConfidenceScorer
from app.orchestration.response_verifier import ResponseVerifier, VerificationReport
from app.orchestration.task_router import RouteDecision, TaskRouter
from app.rag.retriever import build_context_block, retrieve_relevant
from app.security.policies import ensure_input_size, get_policy
from app.security.sanitization import clean_text, redact_secrets, summarize_for_log, truncate
from app.tools.base import ToolContext, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_AUX_OUTPUT_MAX_CHARS = 3000
_MAX_AUX_AGENTS = 2
_MAX_SQUAD_MEMBERS = 8
_SQUAD_PREV_OUTPUT_CHARS = 3500
_SQUAD_CONTEXT_CHARS = 12000


@dataclass
class EngineResult:
    """Resultado completo de una ejecución para la capa API."""

    execution: AgentExecution
    route: RouteDecision
    steps: list[ChainOfWorkStep] = field(default_factory=list)
    verification: VerificationReport | None = None
    confidence: ConfidenceReport | None = None
    tool_results: list[ToolResult] = field(default_factory=list)
    documents_used: int = 0


class ExecutionEngine:
    """Motor de ejecución de agentes con auditoría Chain-of-Work."""

    def __init__(
        self,
        db: Session,
        llm: BaseLLMProvider,
        tool_registry: ToolRegistry,
        agent_registry: AgentRegistry,
        session_factory=None,
    ) -> None:
        self.db = db
        self.llm = llm
        self.tool_registry = tool_registry
        self.agent_registry = agent_registry
        self.model_router = ModelRouter(llm)
        self.task_router = TaskRouter(agent_registry)
        self.planner = AgentPlanner()
        self.verifier = ResponseVerifier()
        self.scorer = ConfidenceScorer()
        self.settings = get_settings()
        # Las herramientas abren sus propias sesiones (ejecutan en otro hilo).
        if session_factory is None:
            from app.database import SessionLocal

            session_factory = SessionLocal
        self.session_factory = session_factory

    # ------------------------------------------------------------------

    def run(
        self,
        task: str,
        agent_name: str | None = None,
        model: str | None = None,
        use_documents: bool = False,
        extra_context: str | None = None,
        username: str = "local",
    ) -> EngineResult:
        """Ejecuta una tarea de principio a fin. No lanza errores de runtime
        del agente/LLM: los refleja en la ejecución con status 'failed'.
        Sí lanza ValueError/PolicyViolation por entradas inválidas (-> HTTP 4xx).
        """
        task = clean_text(task or "").strip()
        if not task:
            raise ValueError("La tarea no puede estar vacía.")
        ensure_input_size(task)
        if extra_context:
            extra_context = clean_text(extra_context)
            ensure_input_size(extra_context)

        # 1-2. Clasificación de intención + selección de agente (puede lanzar
        # ValueError si el agente manual no existe -> 4xx antes de persistir).
        route = self.task_router.route(
            task,
            forced_agent=agent_name,
            llm=self.llm if self.settings.use_llm_intent_fallback else None,
            model=self.settings.default_ollama_model,
            use_llm_fallback=self.settings.use_llm_intent_fallback,
        )
        agent = self.agent_registry.get(route.selected_agent)
        if agent is None:  # defensa extra; el router ya lo garantiza
            raise ValueError(f"Agente no disponible: {route.selected_agent}")

        # 3. Crear la ejecución y la ruta en SQLite.
        execution = AgentExecution(
            agent_name=route.selected_agent,
            selected_by_router=route.selected_by_router,
            intent=route.detected_intent,
            model_provider=self.llm.name,
            model_name=model or agent.default_model or self.settings.default_ollama_model,
            user_input=redact_secrets(task),
            status="running",
        )
        self.db.add(execution)
        self.db.flush()

        self.db.add(
            TaskRoute(
                execution_id=execution.id,
                user_input_summary=summarize_for_log(task, 400),
                detected_intent=route.detected_intent,
                selected_agent=route.selected_agent,
                auxiliary_agents=json.dumps(route.auxiliary_agents, ensure_ascii=False),
                confidence=route.intent_confidence,
                reason=route.reason,
            )
        )

        recorder = ChainOfWorkRecorder(self.db, execution.id, default_agent=route.selected_agent)
        result = EngineResult(execution=execution, route=route)

        recorder.record(
            "task_received",
            "Recepción de tarea",
            description=f"Tarea recibida de '{username}' ({len(task)} caracteres).",
            evidence={"task_summary": summarize_for_log(task, 300), "use_documents": use_documents},
        )
        recorder.record(
            "intent_classification",
            f"Intención detectada: {route.detected_intent}",
            description=f"Método: {route.classification_method}. Confianza: {route.intent_confidence}.",
            evidence={"matched_keywords": route.matched_keywords[:10]},
        )
        recorder.record(
            "agent_selection",
            f"Agente seleccionado: {route.selected_agent}",
            description=route.reason,
            evidence={
                "selected_by_router": route.selected_by_router,
                "auxiliary_agents_proposed": route.auxiliary_agents,
            },
        )

        try:
            self._execute_pipeline(
                execution, route, agent, recorder, result,
                task=task, model=model, use_documents=use_documents, extra_context=extra_context,
            )
        except LLMProviderError as exc:
            self._fail(execution, recorder, result, f"Proveedor LLM: {exc}", risk="high")
        except Exception as exc:  # noqa: BLE001 - frontera del motor: nada debe escapar
            logger.exception("Error inesperado en la ejecución %s", execution.id)
            self._fail(execution, recorder, result, f"Error interno: {exc}", risk="high")

        self.db.commit()
        result.steps = list(execution.steps)
        return result

    # ------------------------------------------------------------------

    def _execute_pipeline(
        self,
        execution: AgentExecution,
        route: RouteDecision,
        agent: BaseAgent,
        recorder: ChainOfWorkRecorder,
        result: EngineResult,
        *,
        task: str,
        model: str | None,
        use_documents: bool,
        extra_context: str | None,
    ) -> None:
        # 4. Resolver modelo (verifica que esté descargado en Ollama).
        model_name = self.model_router.resolve(model, agent.default_model)
        execution.model_name = model_name

        # 5. RAG opcional: recuperar contexto documental.
        documents_block, documents_used = self._retrieve_documents(recorder, task, use_documents)
        result.documents_used = documents_used

        # 6. Contexto del agente + plan auditable.
        ctx = AgentContext(
            task=task,
            model_name=model_name,
            llm=self.llm,
            tools=self.tool_registry,
            tool_context=ToolContext(
                db_session_factory=self.session_factory,
                agent_name=agent.name,
                execution_id=execution.id,
            ),
            extra_context=extra_context,
            documents_block=documents_block,
            documents_used=documents_used,
            recorder=recorder,
            temperature=agent.temperature,
        )
        plan = self.planner.build(agent, ctx)
        recorder.record(
            "work_plan",
            "Plan de trabajo del agente",
            description=plan.objective,
            evidence=plan.to_dict(),
        )

        # 7. Ejecutar agente principal (herramientas + LLM).
        agent_output: AgentOutput = agent.execute(ctx)
        result.tool_results = agent_output.tool_results
        final_output = agent_output.final_output

        # 8. Verificación de la respuesta.
        tools_ok = [r.tool_name for r in agent_output.tool_results if r.ok]
        verification = self.verifier.verify(
            output=final_output,
            agent=agent,
            task=task,
            tools_used=tools_ok,
            documents_used=documents_used,
        )
        result.verification = verification
        recorder.record(
            "response_verification",
            "Validación de la respuesta" + (" superada" if verification.passed else " FALLIDA"),
            description="; ".join(verification.issues) or "Sin observaciones.",
            evidence=[
                {"check": c.name, "passed": c.passed, "detail": c.detail} for c in verification.checks
            ],
            risk_level="info" if verification.passed else "high",
        )

        # 9. Agentes auxiliares (opcional, controlado por configuración).
        if route.auxiliary_agents and self.settings.enable_auxiliary_agents and verification.passed:
            final_output = self._run_auxiliary_agents(
                route, recorder, ctx, final_output
            )
        elif route.auxiliary_agents:
            recorder.record(
                "auxiliary_agent",
                "Agentes auxiliares propuestos (no ejecutados)",
                description=(
                    "Propuestos: "
                    + ", ".join(route.auxiliary_agents)
                    + ". Ejecución desactivada (ENABLE_AUXILIARY_AGENTS=false)."
                ),
            )

        # 10. Confianza.
        tools_failed = sum(1 for r in agent_output.tool_results if not r.ok)
        confidence = self.scorer.score(
            task_chars=len(task) + len(extra_context or ""),
            tools_succeeded=len(tools_ok),
            tools_failed=tools_failed,
            documents_used=documents_used,
            verification=verification,
            uncertainty_declared=agent_output.uncertainty_declared,
            output_chars=len(final_output),
        )
        result.confidence = confidence
        recorder.record(
            "confidence_scoring",
            f"Confianza estimada: {confidence.score}",
            description="; ".join(confidence.notes) or "Sin penalizaciones relevantes.",
            evidence=confidence.breakdown,
        )

        # 11. Cierre de la ejecución.
        status = "completed" if verification.passed else "completed_with_warnings"
        execution.final_output = redact_secrets(final_output)
        execution.confidence_score = confidence.score
        execution.status = status
        execution.finished_at = datetime.now(timezone.utc)
        recorder.record(
            "final_result",
            "Resultado final generado",
            description=(
                f"Estado: {status}. Modelo: {agent_output.model_used}. "
                f"Duración LLM: {agent_output.llm_duration_ms} ms. "
                f"Herramientas OK: {len(tools_ok)}/{len(agent_output.tool_results)}."
            ),
            evidence={"output_chars": len(final_output), "confidence": confidence.score},
        )

    def _retrieve_documents(
        self, recorder: ChainOfWorkRecorder, task: str, use_documents: bool
    ) -> tuple[str, int]:
        """RAG opcional: recupera contexto documental y lo registra. Devuelve (bloque, nº)."""
        if not use_documents:
            return "", 0
        hits = retrieve_relevant(
            self.db,
            task,
            self.settings.rag_top_k,
            provider=self.llm,
            embed_model=self.settings.ollama_embed_model,
            use_embeddings=self.settings.rag_use_embeddings,
        )
        documents_block = build_context_block(hits)
        documents_used = len(hits)
        method = hits[0].method if hits else "keyword"
        recorder.record(
            "document_retrieval",
            f"Recuperación documental ({method}): {documents_used} fragmento(s)",
            description=f"Búsqueda {method} en los documentos locales subidos.",
            evidence=[
                {"filename": h.filename, "chunk": h.chunk_index, "score": round(h.score, 3), "method": h.method}
                for h in hits
            ],
            risk_level="info",
        )
        return documents_block, documents_used

    def _run_auxiliary_agents(
        self,
        route: RouteDecision,
        recorder: ChainOfWorkRecorder,
        primary_ctx: AgentContext,
        final_output: str,
    ) -> str:
        """Ejecuta agentes auxiliares y anexa sus notas a la salida principal."""
        policy = get_policy("standard")
        for aux_name in route.auxiliary_agents[:_MAX_AUX_AGENTS]:
            aux_agent = self.agent_registry.get(aux_name)
            if aux_agent is None:
                continue
            aux_task = (
                "Como agente auxiliar, aporta notas complementarias breves (máximo "
                "10 líneas) a la siguiente tarea ya resuelta por el agente principal. "
                f"Tarea original: {truncate(primary_ctx.task, 600)}"
            )
            aux_ctx = AgentContext(
                task=aux_task,
                model_name=primary_ctx.model_name,
                llm=self.llm,
                tools=self.tool_registry,
                tool_context=primary_ctx.tool_context,
                extra_context=truncate(final_output, 2000),
                recorder=recorder,
                temperature=aux_agent.temperature,
            )
            try:
                aux_output = aux_agent.execute(aux_ctx)
                recorder.record(
                    "auxiliary_agent",
                    f"Agente auxiliar ejecutado: {aux_name}",
                    description=f"Notas complementarias generadas ({len(aux_output.final_output)} caracteres).",
                    agent_name=aux_name,
                    evidence={"max_tool_calls": policy.max_tool_calls},
                )
                final_output += (
                    f"\n\n---\n\n### Notas del agente auxiliar: {aux_agent.display_name}\n\n"
                    + truncate(aux_output.final_output, _AUX_OUTPUT_MAX_CHARS)
                )
            except LLMProviderError as exc:
                recorder.record(
                    "auxiliary_agent",
                    f"Agente auxiliar falló: {aux_name}",
                    description=str(exc),
                    agent_name=aux_name,
                    risk_level="medium",
                )
        return final_output

    # ------------------------------------------------------------------
    # Ejecución multi-agente (squads)
    # ------------------------------------------------------------------

    def run_squad(
        self,
        task: str,
        members: list[str],
        squad_label: str,
        squad_display: str,
        *,
        model: str | None = None,
        use_documents: bool = False,
        extra_context: str | None = None,
        username: str = "local",
        intent: str = "multi_agent",
    ) -> EngineResult:
        """Ejecuta un equipo de agentes en cadena como una única ejecución auditable.

        Cada agente recibe la tarea original más el trabajo acumulado de los
        anteriores. Valida entradas (puede lanzar ValueError/PolicyViolation);
        los errores de runtime se reflejan en la ejecución con status 'failed'.
        """
        task = clean_text(task or "").strip()
        if not task:
            raise ValueError("La tarea no puede estar vacía.")
        ensure_input_size(task)
        if extra_context:
            extra_context = clean_text(extra_context)
            ensure_input_size(extra_context)

        resolved: list[BaseAgent] = []
        for name in members[:_MAX_SQUAD_MEMBERS]:
            agent = self.agent_registry.get(name)
            if agent is None:
                available = ", ".join(self.agent_registry.names())
                raise ValueError(
                    f"Agente desconocido en el equipo: '{name}'. Disponibles: {available}."
                )
            resolved.append(agent)
        if not resolved:
            raise ValueError("El equipo no contiene ningún agente.")

        member_names = [agent.name for agent in resolved]
        execution = AgentExecution(
            agent_name=squad_label,
            selected_by_router=False,
            intent=intent,
            model_provider=self.llm.name,
            model_name=model or self.settings.default_ollama_model,
            user_input=redact_secrets(task),
            status="running",
        )
        self.db.add(execution)
        self.db.flush()

        self.db.add(
            TaskRoute(
                execution_id=execution.id,
                user_input_summary=summarize_for_log(task, 400),
                detected_intent=intent,
                selected_agent=squad_label,
                auxiliary_agents=json.dumps(member_names, ensure_ascii=False),
                confidence=0.0,
                reason=f"Equipo '{squad_display}' con {len(member_names)} agentes en cadena.",
            )
        )

        recorder = ChainOfWorkRecorder(self.db, execution.id, default_agent=squad_label)
        route = RouteDecision(
            detected_intent=intent,
            intent_confidence=0.0,
            classification_method="squad",
            selected_agent=squad_label,
            auxiliary_agents=list(member_names),
            selected_by_router=False,
            reason=f"Ejecución en equipo: {squad_display}.",
        )
        result = EngineResult(execution=execution, route=route)

        recorder.record(
            "task_received",
            "Recepción de tarea (equipo)",
            description=f"Tarea recibida de '{username}' ({len(task)} caracteres).",
            evidence={"task_summary": summarize_for_log(task, 300), "use_documents": use_documents},
        )
        recorder.record(
            "squad_selection",
            f"Equipo seleccionado: {squad_display}",
            description="Agentes en cadena: " + " → ".join(member_names),
            evidence={"members": member_names, "mode": "pipeline"},
        )

        try:
            self._execute_squad_pipeline(
                execution, resolved, recorder, result,
                task=task, model=model, use_documents=use_documents, extra_context=extra_context,
            )
        except LLMProviderError as exc:
            self._fail(execution, recorder, result, f"Proveedor LLM: {exc}", risk="high")
        except Exception as exc:  # noqa: BLE001 - frontera del motor
            logger.exception("Error inesperado en la ejecución de equipo %s", execution.id)
            self._fail(execution, recorder, result, f"Error interno: {exc}", risk="high")

        self.db.commit()
        result.steps = list(execution.steps)
        return result

    def _execute_squad_pipeline(
        self,
        execution: AgentExecution,
        members: list[BaseAgent],
        recorder: ChainOfWorkRecorder,
        result: EngineResult,
        *,
        task: str,
        model: str | None,
        use_documents: bool,
        extra_context: str | None,
    ) -> None:
        model_name = self.model_router.resolve(model, members[0].default_model)
        execution.model_name = model_name

        documents_block, documents_used = self._retrieve_documents(recorder, task, use_documents)
        result.documents_used = documents_used

        accumulated: list[str] = []
        all_tool_results: list[ToolResult] = []
        combined_sections: list[str] = []
        uncertainty_any = False

        for index, agent in enumerate(members, start=1):
            previous_block = ""
            if accumulated:
                previous_block = "\n\n## TRABAJO PREVIO DEL EQUIPO (agentes anteriores)\n" + "\n\n".join(accumulated)
            member_extra = ((extra_context or "") + previous_block).strip() or None
            if member_extra:
                member_extra = truncate(member_extra, _SQUAD_CONTEXT_CHARS)

            ctx = AgentContext(
                task=task,
                model_name=model_name,
                llm=self.llm,
                tools=self.tool_registry,
                tool_context=ToolContext(
                    db_session_factory=self.session_factory,
                    agent_name=agent.name,
                    execution_id=execution.id,
                ),
                extra_context=member_extra,
                documents_block=documents_block,
                documents_used=documents_used,
                recorder=recorder,
                temperature=agent.temperature,
            )
            recorder.record(
                "agent_run",
                f"Agente {index}/{len(members)}: {agent.display_name}",
                description=truncate(agent.description, 300),
                agent_name=agent.name,
                evidence={"position": index, "category": agent.category},
            )

            agent_output: AgentOutput = agent.execute(ctx)
            all_tool_results.extend(agent_output.tool_results)
            uncertainty_any = uncertainty_any or agent_output.uncertainty_declared
            accumulated.append(
                f"### {agent.display_name}\n{truncate(agent_output.final_output, _SQUAD_PREV_OUTPUT_CHARS)}"
            )
            combined_sections.append(
                f"## {agent.display_name} · {agent.category}\n\n{agent_output.final_output}"
            )

        final_output = "\n\n---\n\n".join(combined_sections)

        tools_ok = [r.tool_name for r in all_tool_results if r.ok]
        verification = self.verifier.verify(
            output=final_output,
            agent=members[-1],
            task=task,
            tools_used=tools_ok,
            documents_used=documents_used,
        )
        result.verification = verification
        result.tool_results = all_tool_results
        recorder.record(
            "response_verification",
            "Validación del resultado del equipo" + (" superada" if verification.passed else " FALLIDA"),
            description="; ".join(verification.issues) or "Sin observaciones.",
            evidence=[{"check": c.name, "passed": c.passed, "detail": c.detail} for c in verification.checks],
            risk_level="info" if verification.passed else "high",
        )

        tools_failed = sum(1 for r in all_tool_results if not r.ok)
        confidence = self.scorer.score(
            task_chars=len(task) + len(extra_context or ""),
            tools_succeeded=len(tools_ok),
            tools_failed=tools_failed,
            documents_used=documents_used,
            verification=verification,
            uncertainty_declared=uncertainty_any,
            output_chars=len(final_output),
        )
        result.confidence = confidence
        recorder.record(
            "confidence_scoring",
            f"Confianza estimada: {confidence.score}",
            description="; ".join(confidence.notes) or "Sin penalizaciones relevantes.",
            evidence=confidence.breakdown,
        )

        status = "completed" if verification.passed else "completed_with_warnings"
        execution.final_output = redact_secrets(final_output)
        execution.confidence_score = confidence.score
        execution.status = status
        execution.finished_at = datetime.now(timezone.utc)
        recorder.record(
            "final_result",
            "Resultado del equipo generado",
            description=(
                f"Estado: {status}. {len(members)} agentes ejecutados. "
                f"Herramientas OK: {len(tools_ok)}/{len(all_tool_results)}."
            ),
            evidence={"output_chars": len(final_output), "confidence": confidence.score, "agents": len(members)},
        )

    def _fail(
        self,
        execution: AgentExecution,
        recorder: ChainOfWorkRecorder,
        result: EngineResult,
        message: str,
        risk: str = "high",
    ) -> None:
        execution.status = "failed"
        execution.error_message = summarize_for_log(message, 500)
        execution.finished_at = datetime.now(timezone.utc)
        recorder.record(
            "error",
            "La ejecución falló",
            description=execution.error_message,
            risk_level=risk,
        )
        logger.error(
            "Ejecución fallida",
            extra={"extra_data": {"execution_id": execution.id, "error": execution.error_message}},
        )
