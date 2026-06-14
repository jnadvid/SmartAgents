"""Aplicación FastAPI de la OCS Agentic Enterprise Platform.

Sirve la API local y el frontend estático. Todo funciona sin Docker,
sin servicios cloud y con SQLite + Ollama en local.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import agents, connectors, documents, executions, health, metrics, models, scheduler, tools
from app.config import get_settings, setup_logging
from app.database import SessionLocal, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Arranque: logging, validación de seguridad, BD y registro de agentes."""
    settings = get_settings()
    setup_logging(settings)
    settings.validate_security()
    init_db()

    from app.agents.registry import sync_agents_to_db
    from app.services.agent_runner import get_agent_registry, get_llm_provider

    with SessionLocal() as db:
        sync_agents_to_db(db, get_agent_registry())

    ollama = get_llm_provider().healthcheck()
    logger.info(
        "Plataforma iniciada",
        extra={
            "extra_data": {
                "version": __version__,
                "ollama_status": ollama.status,
                "ollama_models": ollama.models_available,
                "auth_enabled": settings.enable_auth,
            }
        },
    )
    if ollama.status == "down":
        logger.warning(
            "Ollama no está accesible: las ejecuciones fallarán hasta que arranque. "
            "Ejecuta `ollama serve` y descarga un modelo con `ollama pull %s`.",
            settings.default_ollama_model,
        )

    # Programador de tareas en segundo plano (puntual y periódico).
    scheduler_thread = None
    if settings.enable_scheduler:
        from app.scheduler.runner import get_scheduler

        scheduler_thread = get_scheduler()
        scheduler_thread.start()

    yield

    if scheduler_thread is not None:
        scheduler_thread.stop()
    logger.info("Plataforma detenida")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Plataforma local de agentes de IA empresariales, auditables y extensibles. "
            "Backend FastAPI + SQLite + Ollama, sin dependencias cloud."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            f"http://localhost:{settings.app_port}",
            f"http://127.0.0.1:{settings.app_port}",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API (los routers aplican autenticación opcional, /health queda abierto).
    app.include_router(health.router)
    app.include_router(models.router)
    app.include_router(agents.router)
    app.include_router(executions.router)
    app.include_router(documents.router)
    app.include_router(tools.router)
    app.include_router(metrics.router)
    app.include_router(scheduler.router)
    app.include_router(connectors.router)

    # Frontend estático servido en la raíz (después de las rutas de la API).
    frontend_dir = settings.frontend_dir
    if frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    else:  # pragma: no cover - solo si se borra el frontend
        logger.warning("Directorio de frontend no encontrado: %s", frontend_dir)

    return app


app = create_app()
