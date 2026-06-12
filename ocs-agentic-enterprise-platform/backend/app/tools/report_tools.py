"""Herramientas de informes: composición determinista de Markdown."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolContext

# ---------------------------------------------------------------------------
# generate_markdown_report
# ---------------------------------------------------------------------------


class ReportSection(BaseModel):
    heading: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=20000)


class GenerateMarkdownReportInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    sections: list[ReportSection] = Field(min_length=1, max_length=30)
    author: str | None = Field(default=None, max_length=100)
    include_toc: bool = False


class GenerateMarkdownReportTool(BaseTool):
    name = "generate_markdown_report"
    category = "reporting"
    description = "Compone un informe Markdown bien estructurado a partir de título y secciones."
    input_schema = GenerateMarkdownReportInput
    timeout_seconds = 10

    def execute(self, payload: GenerateMarkdownReportInput, ctx: ToolContext) -> dict[str, Any]:
        lines: list[str] = [f"# {payload.title}", ""]
        meta = [f"Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"]
        if payload.author:
            meta.append(f"Autor: {payload.author}")
        lines.append(" | ".join(meta))
        lines.append("")

        if payload.include_toc:
            lines.append("## Índice")
            for index, section in enumerate(payload.sections, start=1):
                lines.append(f"{index}. {section.heading}")
            lines.append("")

        for section in payload.sections:
            lines.append(f"## {section.heading}")
            lines.append("")
            lines.append(section.content.strip() or "_Pendiente de completar._")
            lines.append("")

        markdown = "\n".join(lines).strip() + "\n"
        return {"markdown": markdown, "section_count": len(payload.sections), "chars": len(markdown)}


# ---------------------------------------------------------------------------
# generate_executive_report
# ---------------------------------------------------------------------------


class ExecutiveFinding(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    detail: str = Field(default="", max_length=5000)
    severity: str = Field(default="info", pattern="^(info|low|medium|high|critical)$")


class GenerateExecutiveReportInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=10000)
    findings: list[ExecutiveFinding] = Field(default_factory=list, max_length=50)
    recommendations: list[str] = Field(default_factory=list, max_length=50)
    audience: str = Field(default="dirección", max_length=100)


_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_SEVERITY_LABEL = {
    "critical": "CRÍTICO",
    "high": "ALTO",
    "medium": "MEDIO",
    "low": "BAJO",
    "info": "INFO",
}


class GenerateExecutiveReportTool(BaseTool):
    name = "generate_executive_report"
    category = "reporting"
    description = (
        "Convierte hallazgos y recomendaciones en un informe ejecutivo Markdown "
        "ordenado por severidad, orientado a la audiencia indicada."
    )
    input_schema = GenerateExecutiveReportInput
    timeout_seconds = 10

    def execute(self, payload: GenerateExecutiveReportInput, ctx: ToolContext) -> dict[str, Any]:
        ordered = sorted(payload.findings, key=lambda f: _SEVERITY_ORDER.get(f.severity, 9))
        severity_counts: dict[str, int] = {}
        for finding in payload.findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1

        lines = [
            f"# {payload.title}",
            "",
            f"_Informe ejecutivo para: {payload.audience}_ — "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "",
            "## Resumen ejecutivo",
            "",
            payload.summary.strip() or "_Sin resumen proporcionado._",
            "",
        ]

        if ordered:
            lines += ["## Hallazgos", ""]
            for index, finding in enumerate(ordered, start=1):
                label = _SEVERITY_LABEL.get(finding.severity, finding.severity.upper())
                lines.append(f"### {index}. [{label}] {finding.title}")
                lines.append("")
                if finding.detail.strip():
                    lines.append(finding.detail.strip())
                    lines.append("")

        if payload.recommendations:
            lines += ["## Recomendaciones", ""]
            for recommendation in payload.recommendations:
                lines.append(f"- {recommendation}")
            lines.append("")

        markdown = "\n".join(lines).strip() + "\n"
        return {
            "markdown": markdown,
            "finding_count": len(payload.findings),
            "severity_counts": severity_counts,
        }
