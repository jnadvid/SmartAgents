"""Agente de psicología de la ciberseguridad (factor humano)."""
from __future__ import annotations

from app.agents.base import AgentContext, BaseAgent, ToolInvocationPlan


class CyberpsychologyAnalystAgent(BaseAgent):
    name = "cyberpsychology_analyst"
    display_name = "Psicología de la Ciberseguridad"
    category = "psychology"
    description = (
        "Factor humano en seguridad: susceptibilidad a ingeniería social, cultura de "
        "seguridad, resiliencia ante phishing y cambio de comportamiento (nudges)."
    )
    security_policy = "sensitive"
    data_access = ["local_json", "local_csv"]
    system_prompt = """
Eres especialista en psicología aplicada a la ciberseguridad (factor humano).

Método de trabajo:
- Analizas por qué las personas caen en ingeniería social (sesgos, urgencia,
  autoridad, prueba social) y cómo reforzar la resiliencia, sin culpabilizar al
  usuario: el objetivo es un sistema socio-técnico más seguro.
- Si hay datos de campañas (p. ej. resultados de simulaciones de phishing,
  aportados o conectados), razona solo sobre lo presente; no inventes métricas.
- Propón intervenciones basadas en evidencia (formación situada, nudges,
  fricción útil, refuerzo positivo) y cómo medir su efecto.
- Ética: nada de manipulación dañina; las técnicas son para DEFENDER y educar.
""".strip()
    allowed_tools = ["summarize_text", "extract_action_items", "extract_risks"]
    output_format = [
        "Resumen",
        "Factores humanos y sesgos",
        "Análisis de los datos disponibles",
        "Intervenciones recomendadas",
        "Cultura de seguridad",
        "Cómo medir el impacto",
        "Incertidumbre y límites",
        "Confianza",
    ]

    def plan_tools(self, ctx: AgentContext) -> list[ToolInvocationPlan]:
        combined = f"{ctx.task}\n{ctx.extra_context or ''}".strip()
        return [
            ToolInvocationPlan(
                tool_name="extract_action_items",
                tool_input={"text": combined[:100000]},
                reason="Detectar acciones formativas o de concienciación mencionadas.",
            )
        ]
