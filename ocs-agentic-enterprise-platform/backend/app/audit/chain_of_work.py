"""Chain-of-Work: trazabilidad auditable de cada ejecución.

Principios:
- Se registra QUÉ se hizo (decisiones, herramientas, evidencias, riesgos),
  nunca el razonamiento literal del modelo (chain-of-thought).
- Todo texto pasa por sanitización: sin secretos, sin tokens, truncado.
- Cada paso queda numerado y con marca temporal en SQLite.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import ChainOfWorkStep, ToolLog
from app.security.sanitization import summarize_for_log

logger = logging.getLogger(__name__)

# Tipos de paso normalizados (documentados en docs/chain_of_work.md)
STEP_TYPES = (
    "task_received",
    "intent_classification",
    "agent_selection",
    "work_plan",
    "document_retrieval",
    "llm_call",
    "tool_call",
    "auxiliary_agent",
    "response_verification",
    "confidence_scoring",
    "final_result",
    "error",
)

RISK_LEVELS = ("info", "low", "medium", "high", "critical")

_MAX_FIELD_CHARS = 1000


class ChainOfWorkRecorder:
    """Acumula pasos auditables de una ejecución concreta."""

    def __init__(self, db: Session, execution_id: int, default_agent: str | None = None) -> None:
        self.db = db
        self.execution_id = execution_id
        self.default_agent = default_agent
        self._step_number = 0

    def record(
        self,
        step_type: str,
        title: str,
        description: str = "",
        *,
        agent_name: str | None = None,
        tool_name: str | None = None,
        tool_input_summary: str | None = None,
        tool_output_summary: str | None = None,
        evidence: str | dict[str, Any] | list[Any] | None = None,
        risk_level: str = "info",
    ) -> ChainOfWorkStep:
        """Añade un paso saneado al Chain-of-Work y lo persiste."""
        if step_type not in STEP_TYPES:
            step_type = "error" if step_type == "error" else "final_result" if step_type == "final_result" else step_type
        if risk_level not in RISK_LEVELS:
            risk_level = "info"

        if isinstance(evidence, (dict, list)):
            evidence_text: str | None = json.dumps(evidence, ensure_ascii=False, default=str)
        else:
            evidence_text = evidence

        self._step_number += 1
        step = ChainOfWorkStep(
            execution_id=self.execution_id,
            step_number=self._step_number,
            step_type=step_type,
            title=summarize_for_log(title, 200),
            description=summarize_for_log(description, _MAX_FIELD_CHARS),
            agent_name=agent_name or self.default_agent,
            tool_name=tool_name,
            tool_input_summary=summarize_for_log(tool_input_summary, _MAX_FIELD_CHARS)
            if tool_input_summary
            else None,
            tool_output_summary=summarize_for_log(tool_output_summary, _MAX_FIELD_CHARS)
            if tool_output_summary
            else None,
            evidence=summarize_for_log(evidence_text, _MAX_FIELD_CHARS) if evidence_text else None,
            risk_level=risk_level,
        )
        self.db.add(step)
        self.db.flush()
        logger.debug(
            "Paso Chain-of-Work registrado",
            extra={
                "extra_data": {
                    "execution_id": self.execution_id,
                    "step_number": step.step_number,
                    "step_type": step_type,
                }
            },
        )
        return step

    def record_tool_log(
        self,
        agent_name: str,
        tool_name: str,
        input_summary: str,
        output_summary: str,
        status: str,
        error_message: str | None = None,
    ) -> ToolLog:
        """Registra la ejecución de una herramienta en la tabla ToolLog."""
        log = ToolLog(
            execution_id=self.execution_id,
            agent_name=agent_name,
            tool_name=tool_name,
            input_summary=summarize_for_log(input_summary, _MAX_FIELD_CHARS),
            output_summary=summarize_for_log(output_summary, _MAX_FIELD_CHARS),
            status=status,
            error_message=summarize_for_log(error_message, 500) if error_message else None,
        )
        self.db.add(log)
        self.db.flush()
        return log
