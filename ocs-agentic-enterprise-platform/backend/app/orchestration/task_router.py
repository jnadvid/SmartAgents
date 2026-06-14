"""TaskRouter: de la intención detectada al agente principal y auxiliares."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.agents.registry import AgentRegistry
from app.llm.base import BaseLLMProvider
from app.orchestration.intent_classifier import IntentClassifier, IntentResult

logger = logging.getLogger(__name__)

# Mapa cerrado intención -> agente principal.
INTENT_AGENT_MAP: dict[str, str] = {
    "general_business": "business_assistant",
    "document_writing": "document_writer",
    "document_analysis": "document_audit",
    "data_analysis": "data_analyst",
    "legal_review": "legal_document",
    "sales_proposal": "sales_proposal",
    "market_research": "market_research",
    "finance_analysis": "finance",
    "project_management": "project_manager",
    "hr_training": "hr_training",
    "customer_support": "customer_support",
    "report_generation": "report",
    "cybersecurity_analysis": "cyber_threat_analyst",
    "compliance_analysis": "compliance",
    "vulnerability_triage": "vulnerability_triage",
    "prompt_security_testing": "prompt_injection_tester",
    # Programación
    "software_architecture": "software_architect",
    "backend_development": "backend_developer",
    "frontend_development": "frontend_developer",
    "code_review": "code_reviewer",
    "software_testing": "qa_test_engineer",
    "devops_ci_cd": "devops_engineer",
    "database_engineering": "database_engineer",
    "technical_documentation": "technical_writer",
    # Ciberseguridad (especializada)
    "incident_response": "incident_responder",
    "threat_intelligence": "threat_intel_analyst",
    "application_security": "appsec_engineer",
    # Psicología
    "organizational_psychology": "organizational_psychologist",
    "ux_psychology": "ux_psychologist",
    "wellbeing": "wellbeing_coach",
    # Negocio / operaciones (especializado)
    "business_strategy": "strategy_consultant",
    "operations_management": "operations_manager",
    # RRHH (especializado)
    "recruitment": "recruiter",
    "people_operations": "people_ops",
    # Compliance (especializado)
    "data_protection": "data_protection_officer",
    # Proyectos (especializado)
    "agile_coaching": "agile_coach",
}

# Agentes auxiliares PROPUESTOS por intención (su ejecución es opcional y
# está controlada por ENABLE_AUXILIARY_AGENTS).
AUXILIARY_AGENTS_MAP: dict[str, list[str]] = {
    "cybersecurity_analysis": ["report"],
    "vulnerability_triage": ["report"],
    "compliance_analysis": ["report"],
    "sales_proposal": ["market_research"],
    "market_research": ["report"],
    "finance_analysis": ["report"],
    "data_analysis": ["report"],
    # Programación: el revisor y QA complementan al desarrollo
    "backend_development": ["code_reviewer"],
    "frontend_development": ["code_reviewer"],
    "software_architecture": ["backend_developer"],
    "code_review": ["appsec_engineer"],
    "database_engineering": ["appsec_engineer"],
    # Ciberseguridad especializada
    "incident_response": ["threat_intel_analyst", "report"],
    "threat_intelligence": ["report"],
    "application_security": ["code_reviewer"],
    # Negocio / RRHH / compliance
    "business_strategy": ["market_research"],
    "operations_management": ["report"],
    "recruitment": ["people_ops"],
    "data_protection": ["compliance"],
}

FALLBACK_AGENT = "business_assistant"


@dataclass(frozen=True)
class RouteDecision:
    """Decisión de enrutado de una tarea."""

    detected_intent: str
    intent_confidence: float
    classification_method: str
    selected_agent: str
    auxiliary_agents: list[str] = field(default_factory=list)
    selected_by_router: bool = True
    reason: str = ""
    matched_keywords: list[str] = field(default_factory=list)


class TaskRouter:
    """Selecciona el agente adecuado para una tarea."""

    def __init__(self, agent_registry: AgentRegistry, classifier: IntentClassifier | None = None) -> None:
        self.agent_registry = agent_registry
        self.classifier = classifier or IntentClassifier()

    def _resolve_agent(self, intent: str) -> tuple[str, str]:
        """Devuelve (agente, motivo) para una intención."""
        agent_name = INTENT_AGENT_MAP.get(intent, FALLBACK_AGENT)
        if self.agent_registry.get(agent_name) is None:
            logger.warning("Agente '%s' no registrado; usando fallback", agent_name)
            return FALLBACK_AGENT, (
                f"El agente mapeado para '{intent}' no está disponible; "
                f"se usa el asistente de negocio general."
            )
        return agent_name, f"Intención '{intent}' mapeada al agente '{agent_name}'."

    def _auxiliaries_for(self, intent: str, selected_agent: str) -> list[str]:
        return [
            name
            for name in AUXILIARY_AGENTS_MAP.get(intent, [])
            if name != selected_agent and self.agent_registry.get(name) is not None
        ]

    def route(
        self,
        task: str,
        forced_agent: str | None = None,
        llm: BaseLLMProvider | None = None,
        model: str | None = None,
        use_llm_fallback: bool = False,
    ) -> RouteDecision:
        """Enruta la tarea: modo manual (forced_agent) o automático."""
        intent_result: IntentResult = self.classifier.classify(
            task, llm=llm, model=model, use_llm_fallback=use_llm_fallback
        )

        if forced_agent:
            agent = self.agent_registry.get(forced_agent)
            if agent is None:
                available = ", ".join(self.agent_registry.names())
                raise ValueError(
                    f"Agente desconocido: '{forced_agent}'. Disponibles: {available}."
                )
            return RouteDecision(
                detected_intent=intent_result.intent,
                intent_confidence=intent_result.confidence,
                classification_method=intent_result.method,
                selected_agent=forced_agent,
                auxiliary_agents=[],
                selected_by_router=False,
                reason="Agente seleccionado manualmente por el usuario.",
                matched_keywords=intent_result.matched_keywords,
            )

        selected_agent, reason = self._resolve_agent(intent_result.intent)
        if intent_result.confidence < 0.4:
            reason += " Confianza de clasificación baja: revisar si el agente es el adecuado."

        return RouteDecision(
            detected_intent=intent_result.intent,
            intent_confidence=intent_result.confidence,
            classification_method=intent_result.method,
            selected_agent=selected_agent,
            auxiliary_agents=self._auxiliaries_for(intent_result.intent, selected_agent),
            selected_by_router=True,
            reason=reason,
            matched_keywords=intent_result.matched_keywords,
        )
