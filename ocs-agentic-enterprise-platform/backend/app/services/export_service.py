"""Exportación de ejecuciones (Fase 2): informe Markdown/HTML descargable."""
from __future__ import annotations

import html
import json

from sqlalchemy.orm import Session

from app.models import AgentExecution
from app.services import execution_service

_RISK_EMOJI = {"info": "·", "low": "○", "medium": "◐", "high": "●", "critical": "⛔"}


def build_markdown(db: Session, execution: AgentExecution) -> str:
    """Genera un informe Markdown completo y autocontenido de una ejecución."""
    steps = execution_service.get_chain_of_work(db, execution.id)
    confidence = (
        f"{round(execution.confidence_score * 100)}%"
        if execution.confidence_score is not None
        else "N/D"
    )
    created = execution.created_at.strftime("%Y-%m-%d %H:%M UTC") if execution.created_at else "—"

    lines: list[str] = [
        f"# Informe de ejecución #{execution.id}",
        "",
        f"- **Agente:** {execution.agent_name}",
        f"- **Intención detectada:** {execution.intent}",
        f"- **Selección:** {'automática (router)' if execution.selected_by_router else 'manual'}",
        f"- **Modelo:** {execution.model_provider} / {execution.model_name}",
        f"- **Estado:** {execution.status}",
        f"- **Confianza:** {confidence}",
        f"- **Fecha:** {created}",
        "",
        "## Tarea solicitada",
        "",
        (execution.user_input or "_(vacía)_").strip(),
        "",
        "## Respuesta del agente",
        "",
        (execution.final_output or "_(sin salida)_").strip(),
        "",
        "## Chain-of-Work (trazabilidad auditable)",
        "",
        "| # | Tipo | Título | Riesgo | Herramienta |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in steps:
        emoji = _RISK_EMOJI.get(step.risk_level, "·")
        title = (step.title or "").replace("|", "/")
        lines.append(
            f"| {step.step_number} | {step.step_type} | {title} | "
            f"{emoji} {step.risk_level} | {step.tool_name or ''} |"
        )

    if execution.error_message:
        lines += ["", "## Error", "", f"```\n{execution.error_message}\n```"]

    lines += [
        "",
        "---",
        "_Generado por OCS Agentic Enterprise Platform. "
        "Respuesta orientativa: revísela antes de usarla._",
        "",
    ]
    return "\n".join(lines)


def build_html(db: Session, execution: AgentExecution) -> str:
    """Informe HTML autocontenido (sin dependencias externas)."""
    steps = execution_service.get_chain_of_work(db, execution.id)
    confidence = (
        f"{round(execution.confidence_score * 100)}%"
        if execution.confidence_score is not None
        else "N/D"
    )

    def esc(text: str | None) -> str:
        return html.escape(text or "")

    rows = "\n".join(
        f"<tr><td>{s.step_number}</td><td><code>{esc(s.step_type)}</code></td>"
        f"<td>{esc(s.title)}</td><td>{esc(s.risk_level)}</td>"
        f"<td>{esc(s.tool_name)}</td></tr>"
        for s in steps
    )
    meta = {
        "Agente": execution.agent_name,
        "Intención": execution.intent,
        "Modelo": f"{execution.model_provider} / {execution.model_name}",
        "Estado": execution.status,
        "Confianza": confidence,
    }
    meta_rows = "\n".join(f"<tr><th>{esc(k)}</th><td>{esc(str(v))}</td></tr>" for k, v in meta.items())

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Ejecución #{execution.id} - OCS</title>
<style>
body{{font-family:system-ui,Segoe UI,sans-serif;max-width:900px;margin:30px auto;padding:0 20px;color:#1b2330;line-height:1.55}}
h1{{color:#2563eb}} h2{{color:#1e40af;border-bottom:2px solid #e5e7eb;padding-bottom:4px}}
table{{border-collapse:collapse;width:100%;margin:10px 0;font-size:.9rem}}
th,td{{border:1px solid #e5e7eb;padding:6px 9px;text-align:left}}
th{{background:#f3f4f6}} code{{background:#f3f4f6;padding:1px 5px;border-radius:4px}}
pre{{background:#0e1217;color:#e6edf3;padding:14px;border-radius:8px;white-space:pre-wrap;overflow:auto}}
.foot{{color:#6b7280;font-size:.8rem;margin-top:30px;border-top:1px solid #e5e7eb;padding-top:10px}}
</style></head><body>
<h1>Informe de ejecución #{execution.id}</h1>
<table>{meta_rows}</table>
<h2>Tarea solicitada</h2><pre>{esc(execution.user_input)}</pre>
<h2>Respuesta del agente</h2><pre>{esc(execution.final_output)}</pre>
<h2>Chain-of-Work</h2>
<table><tr><th>#</th><th>Tipo</th><th>Título</th><th>Riesgo</th><th>Herramienta</th></tr>
{rows}</table>
<p class="foot">Generado por OCS Agentic Enterprise Platform. Respuesta orientativa: revísela antes de usarla.</p>
</body></html>
"""
