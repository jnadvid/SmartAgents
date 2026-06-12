"""Agente defensivo de seguridad de prompts (sistemas LLM propios)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class PromptInjectionTesterAgent(BaseAgent):
    name = "prompt_injection_tester"
    display_name = "Seguridad de Prompts"
    category = "security_testing"
    description = (
        "Analiza entradas y prompts en busca de patrones de inyección y "
        "propone hardening. Uso defensivo sobre sistemas propios/autorizados."
    )
    security_policy = "security_testing"
    system_prompt = """
Eres un analista defensivo de seguridad de aplicaciones LLM. Tu función es
evaluar entradas, prompts y diseños de prompts de sistemas PROPIOS o con
autorización expresa, para detectar riesgos de inyección y proponer
mitigaciones.

Límites estrictos:
- NO generes payloads de ataque operativos ni variantes "mejoradas" de las
  inyecciones detectadas; describe el patrón a nivel conceptual.
- Tu objetivo es el hardening: detección, diseño robusto y validación.

Método de trabajo:
- Usa los hallazgos de la herramienta `check_prompt_injection_patterns`
  como evidencia (patrón, categoría, riesgo).
- Evalúa el impacto potencial en el contexto descrito por el usuario
  (qué podría conseguir la inyección si el sistema la obedeciera).
- Propón mitigaciones concretas: separación instrucciones/datos,
  allow-list de herramientas, validación de salida, redacción de secretos.
""".strip()
    allowed_tools = ["check_prompt_injection_patterns", "generate_executive_report"]
    output_format = [
        "Resumen",
        "Patrones detectados",
        "Nivel de riesgo",
        "Impacto potencial",
        "Mitigaciones",
        "Recomendaciones de hardening",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        target = (ctx.extra_context or ctx.task).strip()
        return [
            ToolInvocationPlan(
                tool_name="check_prompt_injection_patterns",
                tool_input={"text": target[:100000]},
                reason="Escanear la entrada con los patrones defensivos de inyección de prompts.",
            )
        ]
