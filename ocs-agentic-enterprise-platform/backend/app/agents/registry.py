"""Registro central de agentes y sincronización con la base de datos."""
from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.models import Agent as AgentModel

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Catálogo en memoria de agentes disponibles (fuente de verdad)."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        if agent.name in self._agents:
            raise ValueError(f"Agente duplicado en el registro: '{agent.name}'")
        self._agents[agent.name] = agent

    def register_all(self, agents: Iterable[BaseAgent]) -> None:
        for agent in agents:
            self.register(agent)

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def names(self) -> list[str]:
        return sorted(self._agents)

    def list_agents(self) -> list[BaseAgent]:
        return [self._agents[name] for name in self.names()]

    def categories(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for agent in self.list_agents():
            result.setdefault(agent.category, []).append(agent.name)
        return result


def build_default_registry() -> AgentRegistry:
    """Construye el registro con los 16 agentes del MVP."""
    from app.agents.business_assistant_agent import BusinessAssistantAgent
    from app.agents.compliance_agent import ComplianceAgent
    from app.agents.customer_support_agent import CustomerSupportAgent
    from app.agents.cyber_threat_analyst_agent import CyberThreatAnalystAgent
    from app.agents.data_analyst_agent import DataAnalystAgent
    from app.agents.document_audit_agent import DocumentAuditAgent
    from app.agents.document_writer_agent import DocumentWriterAgent
    from app.agents.finance_agent import FinanceAgent
    from app.agents.hr_training_agent import HRTrainingAgent
    from app.agents.legal_document_agent import LegalDocumentAgent
    from app.agents.market_research_agent import MarketResearchAgent
    from app.agents.project_manager_agent import ProjectManagerAgent
    from app.agents.prompt_injection_tester_agent import PromptInjectionTesterAgent
    from app.agents.report_agent import ReportAgent
    from app.agents.sales_proposal_agent import SalesProposalAgent
    from app.agents.vulnerability_triage_agent import VulnerabilityTriageAgent

    registry = AgentRegistry()
    registry.register_all(
        [
            BusinessAssistantAgent(),
            DocumentWriterAgent(),
            DataAnalystAgent(),
            LegalDocumentAgent(),
            SalesProposalAgent(),
            MarketResearchAgent(),
            FinanceAgent(),
            ProjectManagerAgent(),
            HRTrainingAgent(),
            CustomerSupportAgent(),
            ReportAgent(),
            CyberThreatAnalystAgent(),
            ComplianceAgent(),
            DocumentAuditAgent(),
            VulnerabilityTriageAgent(),
            PromptInjectionTesterAgent(),
        ]
    )
    return registry


def sync_agents_to_db(db: Session, registry: AgentRegistry) -> None:
    """Refleja el registro de agentes en la tabla `agents` (alta y actualización)."""
    existing = {agent.name: agent for agent in db.execute(select(AgentModel)).scalars()}
    for agent in registry.list_agents():
        row = existing.get(agent.name)
        if row is None:
            db.add(
                AgentModel(
                    name=agent.name,
                    category=agent.category,
                    description=agent.description,
                    enabled=True,
                )
            )
        else:
            row.category = agent.category
            row.description = agent.description
    db.commit()
    logger.info(
        "Agentes sincronizados con la base de datos",
        extra={"extra_data": {"count": len(registry.names())}},
    )
