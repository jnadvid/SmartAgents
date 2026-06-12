"""Agente de investigación de mercado (sin navegación web en el MVP)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class MarketResearchAgent(BaseAgent):
    name = "market_research"
    display_name = "Investigación de Mercado"
    category = "research"
    description = (
        "Analiza empresas, sectores, competidores, oportunidades y "
        "posicionamiento a partir de la información aportada."
    )
    system_prompt = """
Eres un analista de mercado y estrategia competitiva.

ADVERTENCIA OPERATIVA IMPORTANTE: esta plataforma funciona en local y NO
tiene navegación web ni datos de mercado actualizados. Tu análisis debe
basarse EXCLUSIVAMENTE en: (a) la información que aporte el usuario,
(b) los documentos locales recuperados y (c) conocimiento general de
frameworks de análisis (segmentación, posicionamiento, fuerzas competitivas).
Declara siempre esta limitación cuando la tarea pida datos actuales de
mercado, cuotas, precios de competidores o tendencias recientes.

Método de trabajo:
- Si el usuario aporta competidores/alternativas, analízalos; si no,
  no los inventes: pide esos datos en "Preguntas pendientes".
- Usa hipótesis explícitas y marca su nivel de solidez.
""".strip()
    allowed_tools = ["summarize_text", "extract_risks", "search_documents"]
    output_format = [
        "Resumen",
        "Oportunidades",
        "Riesgos",
        "Competidores o alternativas",
        "Propuesta de posicionamiento",
        "Preguntas pendientes",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        text = f"{ctx.task}\n{ctx.extra_context or ''}"
        if len(text) > 1500:
            return [
                ToolInvocationPlan(
                    tool_name="summarize_text",
                    tool_input={"text": text[:100000]},
                    reason="Sintetizar la información de mercado aportada por el usuario.",
                )
            ]
        return []
