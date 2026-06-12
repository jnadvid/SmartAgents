"""Agente auditor de documentos: coherencia, riesgos y calidad."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class DocumentAuditAgent(BaseAgent):
    name = "document_audit"
    display_name = "Auditor de Documentos"
    category = "documents"
    description = (
        "Analiza y audita documentos: resumen, inconsistencias, riesgos, "
        "lagunas y calidad documental."
    )
    system_prompt = """
Eres un auditor documental meticuloso. Analizas documentos (políticas,
procedimientos, informes, actas) buscando inconsistencias, lagunas,
ambigüedades y riesgos.

Método de trabajo:
- Cada hallazgo debe citar el fragmento exacto del documento que lo
  motiva (entre comillas) o la herramienta que lo detectó.
- Tipifica los hallazgos: inconsistencia, laguna, ambigüedad, dato
  desactualizado, riesgo.
- Evalúa si el documento cumple su propósito declarado y si es accionable
  para su audiencia.
- Si solo se aporta un fragmento, limita las conclusiones al fragmento y
  decláralo en "Limitaciones".
""".strip()
    allowed_tools = ["summarize_text", "extract_risks", "search_documents", "summarize_document", "compare_documents"]
    output_format = [
        "Resumen del documento",
        "Hallazgos",
        "Inconsistencias",
        "Riesgos",
        "Recomendaciones",
        "Limitaciones",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        text = f"{ctx.task}\n\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="summarize_text",
                tool_input={"text": text[:100000], "max_sentences": 8},
                reason="Obtener frases clave y métricas del documento a auditar.",
            ),
            ToolInvocationPlan(
                tool_name="extract_risks",
                tool_input={"text": text[:100000]},
                reason="Detectar frases con indicadores de riesgo en el documento.",
            ),
        ]
