"""Endpoints de salud: aplicación y proveedor Ollama."""
from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.config import get_settings
from app.llm.base import LLMProviderError
from app.schemas import HealthResponse, OllamaHealthResponse
from app.services.agent_runner import get_llm_provider

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        app_name=settings.app_name,
        app_env=settings.app_env,
        version=__version__,
        database=settings.resolved_database_url,
        auth_enabled=settings.enable_auth,
    )


@router.get("/health/ollama", response_model=OllamaHealthResponse)
def health_ollama() -> OllamaHealthResponse:
    settings = get_settings()
    provider = get_llm_provider()
    status = provider.healthcheck()

    default_available = False
    if status.status == "up":
        try:
            names = {m.name for m in provider.list_models()}
            default_available = (
                settings.default_ollama_model in names
                or f"{settings.default_ollama_model}:latest" in names
            )
        except LLMProviderError:
            default_available = False

    return OllamaHealthResponse(
        status="up" if status.status == "up" else "down",
        base_url=status.base_url,
        models_available=status.models_available,
        default_model=settings.default_ollama_model,
        default_model_available=default_available,
        detail=status.detail,
    )
