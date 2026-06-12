"""Endpoints de modelos Ollama: listado y prueba rápida."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.llm.base import LLMConnectionError, LLMModelNotFoundError, LLMProviderError
from app.schemas import ModelInfoResponse, ModelTestRequest, ModelTestResponse
from app.security.auth import api_key_auth
from app.services.agent_runner import get_llm_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"], dependencies=[Depends(api_key_auth)])


@router.get("", response_model=list[ModelInfoResponse])
def list_models() -> list[ModelInfoResponse]:
    provider = get_llm_provider()
    try:
        models = provider.list_models()
    except LLMConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [
        ModelInfoResponse(
            name=m.name,
            size_bytes=m.size_bytes,
            modified_at=m.modified_at,
            family=m.family,
            parameter_size=m.parameter_size,
            quantization=m.quantization,
        )
        for m in models
    ]


@router.post("/test", response_model=ModelTestResponse)
def test_model(request: ModelTestRequest) -> ModelTestResponse:
    """Prueba rápida de generación con un modelo (latencia y snippet)."""
    settings = get_settings()
    provider = get_llm_provider()
    model = request.model or settings.default_ollama_model
    try:
        result = provider.generate(
            prompt=request.prompt,
            model=model,
            system_prompt="Responde de forma breve.",
            temperature=0.0,
            max_tokens=64,
        )
    except LLMModelNotFoundError as exc:
        return ModelTestResponse(ok=False, model=model, error=str(exc))
    except LLMProviderError as exc:
        return ModelTestResponse(ok=False, model=model, error=str(exc))
    return ModelTestResponse(
        ok=True,
        model=model,
        latency_ms=result.duration_ms,
        output_snippet=result.text[:200],
    )
