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
    """Construye el registro con los 49 agentes especializados por áreas."""
    from app.agents.ad_pentester_agent import AdPentesterAgent
    from app.agents.agile_coach_agent import AgileCoachAgent
    from app.agents.api_pentester_agent import ApiPentesterAgent
    from app.agents.appsec_engineer_agent import AppSecEngineerAgent
    from app.agents.network_pentester_agent import NetworkPentesterAgent
    from app.agents.backend_developer_agent import BackendDeveloperAgent
    from app.agents.blue_team_analyst_agent import BlueTeamAnalystAgent
    from app.agents.business_assistant_agent import BusinessAssistantAgent
    from app.agents.code_reviewer_agent import CodeReviewerAgent
    from app.agents.compliance_agent import ComplianceAgent
    from app.agents.customer_support_agent import CustomerSupportAgent
    from app.agents.cyber_threat_analyst_agent import CyberThreatAnalystAgent
    from app.agents.cyberpsychology_analyst_agent import CyberpsychologyAnalystAgent
    from app.agents.data_analyst_agent import DataAnalystAgent
    from app.agents.data_protection_officer_agent import DataProtectionOfficerAgent
    from app.agents.database_engineer_agent import DatabaseEngineerAgent
    from app.agents.detection_engineer_agent import DetectionEngineerAgent
    from app.agents.devops_engineer_agent import DevOpsEngineerAgent
    from app.agents.document_audit_agent import DocumentAuditAgent
    from app.agents.document_writer_agent import DocumentWriterAgent
    from app.agents.finance_agent import FinanceAgent
    from app.agents.frontend_developer_agent import FrontendDeveloperAgent
    from app.agents.hr_training_agent import HRTrainingAgent
    from app.agents.incident_responder_agent import IncidentResponderAgent
    from app.agents.legal_document_agent import LegalDocumentAgent
    from app.agents.market_research_agent import MarketResearchAgent
    from app.agents.operations_manager_agent import OperationsManagerAgent
    from app.agents.organizational_psychologist_agent import OrganizationalPsychologistAgent
    from app.agents.ot_security_analyst_agent import OtSecurityAnalystAgent
    from app.agents.pentest_lead_agent import PentestLeadAgent
    from app.agents.people_ops_agent import PeopleOpsAgent
    from app.agents.project_manager_agent import ProjectManagerAgent
    from app.agents.prompt_injection_tester_agent import PromptInjectionTesterAgent
    from app.agents.purple_team_lead_agent import PurpleTeamLeadAgent
    from app.agents.qa_test_engineer_agent import QATestEngineerAgent
    from app.agents.recruiter_agent import RecruiterAgent
    from app.agents.red_team_operator_agent import RedTeamOperatorAgent
    from app.agents.report_agent import ReportAgent
    from app.agents.sales_proposal_agent import SalesProposalAgent
    from app.agents.soc_manager_agent import SocManagerAgent
    from app.agents.software_architect_agent import SoftwareArchitectAgent
    from app.agents.strategy_consultant_agent import StrategyConsultantAgent
    from app.agents.technical_writer_agent import TechnicalWriterAgent
    from app.agents.threat_hunter_agent import ThreatHunterAgent
    from app.agents.threat_intel_analyst_agent import ThreatIntelAnalystAgent
    from app.agents.ux_psychologist_agent import UXPsychologistAgent
    from app.agents.vulnerability_triage_agent import VulnerabilityTriageAgent
    from app.agents.web_pentester_agent import WebPentesterAgent
    from app.agents.wellbeing_coach_agent import WellbeingCoachAgent

    registry = AgentRegistry()
    registry.register_all(
        [
            # --- Negocio ---
            BusinessAssistantAgent(),
            StrategyConsultantAgent(),
            OperationsManagerAgent(),
            # --- Documentos / datos / investigación ---
            DocumentWriterAgent(),
            DocumentAuditAgent(),
            DataAnalystAgent(),
            MarketResearchAgent(),
            ReportAgent(),
            # --- Ventas / finanzas / legal ---
            SalesProposalAgent(),
            FinanceAgent(),
            LegalDocumentAgent(),
            # --- Proyectos ---
            ProjectManagerAgent(),
            AgileCoachAgent(),
            # --- RRHH ---
            HRTrainingAgent(),
            RecruiterAgent(),
            PeopleOpsAgent(),
            # --- Soporte ---
            CustomerSupportAgent(),
            # --- Programación ---
            SoftwareArchitectAgent(),
            BackendDeveloperAgent(),
            FrontendDeveloperAgent(),
            CodeReviewerAgent(),
            QATestEngineerAgent(),
            DevOpsEngineerAgent(),
            DatabaseEngineerAgent(),
            TechnicalWriterAgent(),
            # --- Ciberseguridad ---
            CyberThreatAnalystAgent(),
            VulnerabilityTriageAgent(),
            IncidentResponderAgent(),
            ThreatIntelAnalystAgent(),
            AppSecEngineerAgent(),
            PromptInjectionTesterAgent(),
            # Blue / Red / Purple Team, SOC y OT
            SocManagerAgent(),
            BlueTeamAnalystAgent(),
            ThreatHunterAgent(),
            DetectionEngineerAgent(),
            RedTeamOperatorAgent(),
            PurpleTeamLeadAgent(),
            OtSecurityAnalystAgent(),
            WebPentesterAgent(),
            PentestLeadAgent(),
            NetworkPentesterAgent(),
            AdPentesterAgent(),
            ApiPentesterAgent(),
            # --- Compliance ---
            ComplianceAgent(),
            DataProtectionOfficerAgent(),
            # --- Psicología ---
            OrganizationalPsychologistAgent(),
            UXPsychologistAgent(),
            WellbeingCoachAgent(),
            CyberpsychologyAnalystAgent(),
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
