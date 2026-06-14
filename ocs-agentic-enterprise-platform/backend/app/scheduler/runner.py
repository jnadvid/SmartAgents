"""Hilo en segundo plano del programador de tareas.

Cada `poll_seconds` abre una sesión, ejecuta las tareas vencidas y vuelve a
dormir. Es robusto: ninguna excepción de una tarea tumba el bucle ni la app.
No usa `sleep` bloqueante: espera sobre un Event para poder pararse limpio.
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


class SchedulerThread:
    """Planificador en proceso, sin dependencias externas."""

    def __init__(self, poll_seconds: int | None = None) -> None:
        from app.config import get_settings

        self.poll_seconds = poll_seconds or get_settings().scheduler_poll_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="ocs-scheduler", daemon=True)
        self._thread.start()
        logger.info("Programador de tareas iniciado", extra={"extra_data": {"poll_seconds": self.poll_seconds}})

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("Programador de tareas detenido")

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _loop(self) -> None:
        # Espera inicial para no competir con el arranque de la app.
        while not self._stop.wait(self.poll_seconds):
            self._tick()

    def _tick(self) -> None:
        try:
            from app.database import SessionLocal
            from app.services import scheduler_service
            from app.services.agent_runner import (
                get_agent_registry,
                get_llm_provider,
                get_tool_registry,
            )

            with SessionLocal() as db:
                runs = scheduler_service.run_due(
                    db,
                    llm=get_llm_provider(),
                    tool_registry=get_tool_registry(),
                    agent_registry=get_agent_registry(),
                    session_factory=SessionLocal,
                )
            if runs:
                logger.info("Programador: %d tarea(s) ejecutada(s)", len(runs))
        except Exception:  # noqa: BLE001 - el bucle nunca debe morir
            logger.exception("Error en el ciclo del programador de tareas")


_scheduler: SchedulerThread | None = None


def get_scheduler() -> SchedulerThread:
    """Singleton de proceso del planificador."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerThread()
    return _scheduler
