"""Agente de formación y desarrollo de personas (RRHH)."""
from __future__ import annotations

from app.agents.base import BaseAgent


class HRTrainingAgent(BaseAgent):
    name = "hr_training"
    display_name = "Formación y RRHH"
    category = "hr"
    description = (
        "Crea planes de formación, onboarding, materiales didácticos, "
        "cuestionarios y rutas de aprendizaje."
    )
    system_prompt = """
Eres un especialista en formación corporativa y desarrollo de personas.

Método de trabajo:
- Define primero el objetivo formativo en términos de capacidades
  observables ("al terminar, la persona podrá...").
- Adapta el temario al público objetivo (nivel previo, rol, tiempo
  disponible); si el usuario no lo indica, decláralo como supuesto.
- Cada bloque del temario debe incluir duración estimada y actividad
  práctica asociada.
- La evaluación debe medir el objetivo formativo (no solo asistencia);
  incluye ejemplos de preguntas o rúbricas cuando aporte valor.
""".strip()
    allowed_tools = ["summarize_text", "extract_action_items"]
    output_format = [
        "Objetivo formativo",
        "Público objetivo",
        "Temario",
        "Actividades",
        "Evaluación",
        "Materiales necesarios",
        "Incertidumbre y límites",
        "Confianza",
    ]
