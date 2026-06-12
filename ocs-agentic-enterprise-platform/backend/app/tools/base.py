"""Base del sistema de herramientas.

Reglas de seguridad (aplicadas por diseño):
- Las herramientas son funciones puras sobre texto/datos: no ejecutan
  comandos del sistema ni acceden a Internet.
- Solo pueden leer/escribir datos a través de la base de datos local
  (que vive en backend/data).
- Toda entrada se valida con Pydantic y toda ejecución tiene timeout.
- El resultado siempre vuelve como ToolResult, nunca como excepción.
"""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.security.sanitization import summarize_for_log

logger = logging.getLogger(__name__)


class ToolError(Exception):
    """Error genérico de herramienta."""


class ToolValidationError(ToolError):
    """La entrada de la herramienta no supera la validación."""


class ToolExecutionError(ToolError):
    """La herramienta falló durante su ejecución."""


@dataclass
class ToolContext:
    """Contexto de ejecución inyectado en las herramientas.

    `db_session_factory` permite a herramientas documentales abrir sesiones
    contra la base local sin acoplarse al motor global (clave para tests).
    """

    db_session_factory: Callable[[], Session] | None = None
    agent_name: str | None = None
    execution_id: int | None = None


@dataclass
class ToolResult:
    """Resultado normalizado de la ejecución de una herramienta."""

    tool_name: str
    status: str  # "success" | "error" | "timeout" | "denied"
    output: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    error_message: str | None = None
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "success"


class BaseTool(ABC):
    """Herramienta base: validación de entrada, timeout y salida normalizada."""

    name: str = "base_tool"
    category: str = "general"
    description: str = ""
    input_schema: type[BaseModel]
    required_role: str = "user"
    timeout_seconds: int = 10

    @abstractmethod
    def execute(self, payload: BaseModel, ctx: ToolContext) -> dict[str, Any]:
        """Lógica de la herramienta. Recibe entrada ya validada."""

    # ------------------------------------------------------------------

    def summarize_output(self, output: dict[str, Any]) -> str:
        """Resumen corto y seguro del resultado para auditoría."""
        return summarize_for_log(json.dumps(output, ensure_ascii=False, default=str), 400)

    def run(self, raw_input: dict[str, Any], ctx: ToolContext | None = None) -> ToolResult:
        """Punto de entrada controlado: valida, ejecuta con timeout y normaliza."""
        ctx = ctx or ToolContext()
        started = time.monotonic()

        try:
            payload = self.input_schema.model_validate(raw_input or {})
        except ValidationError as exc:
            detail = "; ".join(
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
            )
            return ToolResult(
                tool_name=self.name,
                status="error",
                error_message=f"Entrada inválida: {detail}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        # Timeout mediante hilo dedicado. Limitación conocida (documentada):
        # un hilo en Python no puede matarse; si la herramienta excede el
        # timeout se devuelve 'timeout' y el hilo termina en segundo plano.
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"tool-{self.name}")
        try:
            future = executor.submit(self.execute, payload, ctx)
            output = future.result(timeout=self.timeout_seconds)
        except FutureTimeoutError:
            logger.warning(
                "Timeout de herramienta",
                extra={"extra_data": {"tool": self.name, "timeout_s": self.timeout_seconds}},
            )
            return ToolResult(
                tool_name=self.name,
                status="timeout",
                error_message=f"La herramienta superó el timeout de {self.timeout_seconds}s.",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 - frontera controlada de tools
            logger.exception("Error ejecutando herramienta %s", self.name)
            return ToolResult(
                tool_name=self.name,
                status="error",
                error_message=summarize_for_log(str(exc), 300),
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if not isinstance(output, dict):
            return ToolResult(
                tool_name=self.name,
                status="error",
                error_message="La herramienta devolvió un tipo inesperado (se esperaba dict).",
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        return ToolResult(
            tool_name=self.name,
            status="success",
            output=output,
            summary=self.summarize_output(output),
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    def describe(self) -> dict[str, Any]:
        """Descripción pública de la herramienta (para la API y el frontend)."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "required_role": self.required_role,
            "timeout_seconds": self.timeout_seconds,
            "input_schema": self.input_schema.model_json_schema(),
        }
