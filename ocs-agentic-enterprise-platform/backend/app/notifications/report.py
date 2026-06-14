"""Informe corporativo en HTML (portada con logo, resumen y cuerpo).

Autocontenido (CSS embebido), apto para email e impresión/PDF. La marca
(empresa, logo, pie) se toma de los ajustes de runtime.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from app import runtime_config

_SEV_COLOR = {"critical": "#b3261e", "high": "#e8590c", "medium": "#f6b545",
              "low": "#3b82f6", "info": "#6b7280"}


def _esc(text: str) -> str:
    return html.escape(text or "")


def _md_to_html(md: str) -> str:
    """Render mínimo de Markdown a HTML (encabezados, listas, negrita, código)."""
    lines = _esc(md or "").split("\n")
    out: list[str] = []
    in_ul = in_ol = in_code = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul: out.append("</ul>"); in_ul = False
        if in_ol: out.append("</ol>"); in_ol = False

    def inline(t: str) -> str:
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        return re.sub(r"`([^`]+)`", r"<code>\1</code>", t)

    for line in lines:
        if line.strip().startswith("```"):
            close_lists()
            out.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            out.append(line)
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            close_lists()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
        elif re.match(r"^\s*[-*]\s+(.*)$", line):
            if in_ol: out.append("</ol>"); in_ol = False
            if not in_ul: out.append("<ul>"); in_ul = True
            item = re.sub(r"^\s*[-*]\s+", "", line)
            out.append(f"<li>{inline(item)}</li>")
        elif re.match(r"^\s*\d+[.)]\s+(.*)$", line):
            if in_ul: out.append("</ul>"); in_ul = False
            if not in_ol: out.append("<ol>"); in_ol = True
            item = re.sub(r"^\s*\d+[.)]\s+", "", line)
            out.append(f"<li>{inline(item)}</li>")
        elif re.match(r"^\s*(---|\*\*\*)\s*$", line):
            close_lists(); out.append("<hr/>")
        elif not line.strip():
            close_lists()
        else:
            close_lists(); out.append(f"<p>{inline(line)}</p>")
    close_lists()
    if in_code: out.append("</code></pre>")
    return "\n".join(out)


_CSS = """
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, Arial, sans-serif; color: #1f2937; margin: 0; background: #fff; line-height: 1.5; }
.cover { padding: 60px 56px; background: linear-gradient(135deg, #0b2447, #19376d); color: #fff; }
.cover .logo { max-height: 64px; margin-bottom: 28px; }
.cover h1 { font-size: 30px; margin: 0 0 6px; }
.cover .sub { color: #b9c7e0; font-size: 15px; }
.meta { margin-top: 30px; display: grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; }
.meta div { font-size: 14px; } .meta b { color: #d7e3f7; }
.sev-row { margin-top: 26px; display: flex; flex-wrap: wrap; gap: 8px; }
.sev { padding: 5px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; color: #fff; }
.content { padding: 36px 56px; }
.content h1 { font-size: 22px; border-bottom: 2px solid #e5e7eb; padding-bottom: 6px; margin-top: 28px; }
.content h2 { font-size: 18px; color: #19376d; margin-top: 24px; }
.content h3 { font-size: 15px; margin-top: 18px; }
.content code { background: #f3f4f6; padding: 1px 5px; border-radius: 4px; font-size: 13px; }
.content pre { background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: 12.5px; }
table.findings { width: 100%; border-collapse: collapse; margin: 12px 0 24px; font-size: 13px; }
table.findings th, table.findings td { border: 1px solid #e5e7eb; padding: 7px 9px; text-align: left; vertical-align: top; }
table.findings th { background: #f3f4f6; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 6px; color: #fff; font-size: 11px; font-weight: 600; }
.footer { padding: 18px 56px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 12px; }
@media print { .cover { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
"""


def _cover_meta(rows: list[tuple[str, str]]) -> str:
    return "".join(f"<div><b>{_esc(k)}:</b> {_esc(v)}</div>" for k, v in rows if v)


def corporate_html(*, title: str, subtitle: str, body_html: str,
                   cover_rows: list[tuple[str, str]], severity_summary: dict[str, int] | None = None,
                   findings_table: str = "") -> str:
    company = str(runtime_config.effective("company_name") or "")
    logo = str(runtime_config.effective("report_logo_url") or "")
    footer = str(runtime_config.effective("report_footer") or "")
    logo_html = f'<img class="logo" src="{_esc(logo)}" alt="logo"/>' if logo else ""
    sev_html = ""
    if severity_summary:
        chips = [
            f'<span class="sev" style="background:{_SEV_COLOR.get(sev, "#6b7280")}">{sev}: {count}</span>'
            for sev, count in severity_summary.items() if count
        ]
        if chips:
            sev_html = '<div class="sev-row">' + "".join(chips) + "</div>"
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"/>
<title>{_esc(title)}</title><style>{_CSS}</style></head><body>
<section class="cover">{logo_html}
  <h1>{_esc(title)}</h1><div class="sub">{_esc(subtitle)}</div>
  <div class="meta">{_cover_meta(cover_rows)}</div>{sev_html}
</section>
<section class="content">{findings_table}{body_html}</section>
<div class="footer">{_esc(company)}{' · ' if company and footer else ''}{_esc(footer)}</div>
</body></html>"""


def _findings_table(findings) -> str:
    if not findings:
        return ""
    rows = []
    for f in findings[:60]:
        color = _SEV_COLOR.get(f.severity, "#6b7280")
        rows.append(
            f'<tr><td><span class="badge" style="background:{color}">{_esc(f.severity)}</span></td>'
            f"<td>{_esc(f.title)}</td><td>{_esc(f.cve)}</td><td>{_esc(f.tool)}</td></tr>"
        )
    return (
        '<h1>Hallazgos priorizados</h1><table class="findings">'
        "<tr><th>Severidad</th><th>Hallazgo</th><th>CVE</th><th>Herramienta</th></tr>"
        + "".join(rows) + "</table>"
    )


def pentest_report_html(*, host: str, profile: str, report_markdown: str,
                        max_severity: str = "info", by_severity: dict[str, int] | None = None,
                        findings=None) -> str:
    company = str(runtime_config.effective("company_name") or "Equipo de Seguridad")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return corporate_html(
        title="Informe de Test de Intrusión",
        subtitle=f"Objetivo autorizado: {host}",
        cover_rows=[("Empresa", company), ("Objetivo", host), ("Perfil", profile or "—"),
                    ("Severidad máxima", max_severity), ("Fecha", now)],
        severity_summary=by_severity,
        findings_table=_findings_table(findings or []),
        body_html=_md_to_html(report_markdown),
    )
