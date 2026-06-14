"""Registro central de herramientas.

El registro es la única vía por la que los agentes ejecutan herramientas:
aplica la lista de autorizaciones del agente y devuelve siempre ToolResult.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

from app.tools.base import BaseTool, ToolContext, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Catálogo de herramientas registradas, indexadas por nombre."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Herramienta duplicada en el registro: '{tool.name}'")
        self._tools[tool.name] = tool

    def register_all(self, tools: Iterable[BaseTool]) -> None:
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def list_tools(self) -> list[BaseTool]:
        return [self._tools[name] for name in self.names()]

    def categories(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for tool in self.list_tools():
            result.setdefault(tool.category, []).append(tool.name)
        return result

    def run_tool(
        self,
        name: str,
        raw_input: dict[str, Any],
        ctx: ToolContext | None = None,
        allowed_tools: list[str] | None = None,
    ) -> ToolResult:
        """Ejecuta una herramienta aplicando la autorización del agente.

        Si `allowed_tools` no es None, la herramienta debe estar incluida;
        en caso contrario se devuelve un resultado 'denied' (y se audita).
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                tool_name=name,
                status="error",
                error_message=f"Herramienta desconocida: '{name}'.",
            )
        if allowed_tools is not None and name not in allowed_tools:
            logger.warning(
                "Herramienta denegada por política",
                extra={"extra_data": {"tool": name, "agent": ctx.agent_name if ctx else None}},
            )
            return ToolResult(
                tool_name=name,
                status="denied",
                error_message="Herramienta no autorizada para este agente.",
            )
        return tool.run(raw_input, ctx)


def build_default_registry() -> ToolRegistry:
    """Construye el registro con las 24 herramientas (19 base + 5 de programación)."""
    # Imports locales para evitar ciclos de importación.
    from app.tools.business_tools import ClassifyCustomerRequestTool, ExtractRisksTool
    from app.tools.code_tools import (
        AnalyzeCodeStructureTool,
        ExtractCodeTodosTool,
        GenerateTestSkeletonTool,
        ReviewCodeQualityTool,
        ScanCodeSecurityTool,
    )
    from app.tools.compliance_tools import GenerateComplianceGapTool
    from app.tools.cyber_tools import (
        CalculateCvssPriorityTool,
        MapToMitreAttackTool,
        ParseWazuhAlertTool,
    )
    from app.tools.data_tools import AnalyzeTableTextTool
    from app.tools.document_tools import (
        CompareDocumentsTool,
        ExtractActionItemsTool,
        SearchDocumentsTool,
        SummarizeDocumentTool,
        SummarizeTextTool,
    )
    from app.tools.finance_tools import CalculateBasicFinancialsTool
    from app.tools.legal_tools import ReviewContractTextTool
    from app.tools.project_tools import CreateProjectPlanTool
    from app.tools.prompt_security_tools import CheckPromptInjectionPatternsTool
    from app.tools.report_tools import GenerateExecutiveReportTool, GenerateMarkdownReportTool
    from app.tools.sales_tools import CreateSalesProposalTool

    registry = ToolRegistry()
    registry.register_all(
        [
            # Generales / documentales
            SummarizeTextTool(),
            ExtractActionItemsTool(),
            SearchDocumentsTool(),
            SummarizeDocumentTool(),
            CompareDocumentsTool(),
            # Datos
            AnalyzeTableTextTool(),
            # Negocio
            ExtractRisksTool(),
            ClassifyCustomerRequestTool(),
            # Ventas
            CreateSalesProposalTool(),
            # Finanzas
            CalculateBasicFinancialsTool(),
            # Legal
            ReviewContractTextTool(),
            # Proyectos
            CreateProjectPlanTool(),
            # Informes
            GenerateMarkdownReportTool(),
            GenerateExecutiveReportTool(),
            # Ciberseguridad
            ParseWazuhAlertTool(),
            MapToMitreAttackTool(),
            CalculateCvssPriorityTool(),
            # Compliance
            GenerateComplianceGapTool(),
            # Seguridad de prompts
            CheckPromptInjectionPatternsTool(),
            # Programación (análisis estático determinista, sin ejecución)
            AnalyzeCodeStructureTool(),
            ReviewCodeQualityTool(),
            ScanCodeSecurityTool(),
            GenerateTestSkeletonTool(),
            ExtractCodeTodosTool(),
        ]
    )
    return registry
