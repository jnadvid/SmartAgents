"""Proveedor LLM basado en la API local de Ollama (http://localhost:11434).

Endpoints usados:
- GET  /api/tags        -> list_models / healthcheck
- POST /api/generate    -> generate
- POST /api/chat        -> chat
- POST /api/show        -> get_model_info
- POST /api/embed       -> embed (con fallback a /api/embeddings)

Maneja explícitamente: Ollama caído, modelo no descargado, timeouts,
errores HTTP, JSON inválido y respuestas vacías.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.config import get_settings
from app.llm.base import (
    BaseLLMProvider,
    ChatMessage,
    GenerationResult,
    LLMConnectionError,
    LLMEmptyResponseError,
    LLMInvalidResponseError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMTimeoutError,
    ModelInfo,
    ProviderHealth,
)

logger = logging.getLogger(__name__)

_HEALTH_TIMEOUT_SECONDS = 5.0


class OllamaProvider(BaseLLMProvider):
    """Cliente síncrono de la API local de Ollama."""

    name = "ollama"

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        settings = get_settings()
        self.base_url: str = (base_url or settings.ollama_base_url).rstrip("/")
        self.timeout: float = float(timeout or settings.ollama_timeout)

    # ------------------------------------------------------------------
    # Infraestructura HTTP
    # ------------------------------------------------------------------

    def _client(self, timeout: float | None = None) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=timeout or self.timeout)

    def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Petición HTTP con traducción de errores a la jerarquía LLM*Error."""
        try:
            with self._client(timeout) as client:
                response = client.request(method, path, json=json_body)
        except httpx.ConnectError as exc:
            raise LLMConnectionError(
                f"No se puede conectar con Ollama en {self.base_url}. "
                "¿Está levantado? Ejecuta `ollama serve`."
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"Timeout de {timeout or self.timeout:.0f}s hablando con Ollama "
                f"({method} {path}). Prueba un modelo más pequeño o sube OLLAMA_TIMEOUT."
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMConnectionError(f"Error de red con Ollama: {exc}") from exc

        if response.status_code == 404:
            detail = self._safe_error_detail(response)
            if "model" in detail.lower() or "not found" in detail.lower():
                raise LLMModelNotFoundError(
                    f"Modelo no disponible en Ollama: {detail}. "
                    "Descárgalo con `ollama pull <modelo>`."
                )
            raise LLMProviderError(f"Recurso no encontrado en Ollama: {detail}")

        if response.status_code >= 400:
            detail = self._safe_error_detail(response)
            raise LLMProviderError(
                f"Ollama devolvió HTTP {response.status_code}: {detail}"
            )

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMInvalidResponseError(
                f"Ollama devolvió una respuesta no JSON en {path}: "
                f"{response.text[:200]!r}"
            ) from exc

        if not isinstance(data, dict):
            raise LLMInvalidResponseError(
                f"Respuesta JSON inesperada de Ollama en {path}: {type(data).__name__}"
            )
        return data

    @staticmethod
    def _safe_error_detail(response: httpx.Response) -> str:
        try:
            body = response.json()
            if isinstance(body, dict) and "error" in body:
                return str(body["error"])
        except (json.JSONDecodeError, ValueError):
            pass
        return response.text[:300] or f"HTTP {response.status_code}"

    @staticmethod
    def _build_options(temperature: float, max_tokens: int | None) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        return options

    # ------------------------------------------------------------------
    # API pública del proveedor
    # ------------------------------------------------------------------

    def healthcheck(self) -> ProviderHealth:
        """Comprueba el estado de Ollama sin lanzar excepciones."""
        try:
            data = self._request("GET", "/api/tags", timeout=_HEALTH_TIMEOUT_SECONDS)
            models = data.get("models") or []
            return ProviderHealth(
                status="up", base_url=self.base_url, models_available=len(models)
            )
        except LLMProviderError as exc:
            return ProviderHealth(status="down", base_url=self.base_url, detail=str(exc))

    def list_models(self) -> list[ModelInfo]:
        data = self._request("GET", "/api/tags")
        models_raw = data.get("models")
        if models_raw is None:
            raise LLMInvalidResponseError("Respuesta de /api/tags sin campo 'models'.")
        models: list[ModelInfo] = []
        for item in models_raw:
            if not isinstance(item, dict) or "name" not in item:
                continue
            details = item.get("details") or {}
            models.append(
                ModelInfo(
                    name=str(item["name"]),
                    size_bytes=item.get("size"),
                    modified_at=item.get("modified_at"),
                    family=details.get("family"),
                    parameter_size=details.get("parameter_size"),
                    quantization=details.get("quantization_level"),
                    raw=item,
                )
            )
        return models

    def get_model_info(self, model: str) -> ModelInfo:
        """Información detallada de un modelo vía /api/show."""
        if not model or not model.strip():
            raise LLMProviderError("Nombre de modelo vacío.")
        data = self._request("POST", "/api/show", json_body={"name": model})
        details = data.get("details") or {}
        return ModelInfo(
            name=model,
            family=details.get("family"),
            parameter_size=details.get("parameter_size"),
            quantization=details.get("quantization_level"),
            raw={k: v for k, v in data.items() if k != "modelfile"},
        )

    def is_model_available(self, model: str) -> bool:
        """True si el modelo (o su variante :latest) está descargado."""
        try:
            names = {m.name for m in self.list_models()}
        except LLMProviderError:
            return False
        return model in names or f"{model}:latest" in names

    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        if not prompt or not prompt.strip():
            raise LLMProviderError("Prompt vacío: no hay nada que generar.")
        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": self._build_options(temperature, max_tokens),
        }
        if system_prompt:
            body["system"] = system_prompt

        started = time.monotonic()
        data = self._request("POST", "/api/generate", json_body=body)
        duration_ms = int((time.monotonic() - started) * 1000)

        text = str(data.get("response") or "").strip()
        if not text:
            raise LLMEmptyResponseError(
                f"El modelo '{model}' devolvió una respuesta vacía en /api/generate."
            )
        logger.info(
            "Generación completada",
            extra={"extra_data": {"model": model, "duration_ms": duration_ms}},
        )
        return GenerationResult(
            text=text,
            model=model,
            provider=self.name,
            duration_ms=duration_ms,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
        )

    def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        if not messages:
            raise LLMProviderError("Lista de mensajes vacía: no hay nada que enviar.")
        for msg in messages:
            if "role" not in msg or "content" not in msg:
                raise LLMProviderError("Cada mensaje debe incluir 'role' y 'content'.")

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": self._build_options(temperature, max_tokens),
        }

        started = time.monotonic()
        data = self._request("POST", "/api/chat", json_body=body)
        duration_ms = int((time.monotonic() - started) * 1000)

        message = data.get("message")
        text = ""
        if isinstance(message, dict):
            text = str(message.get("content") or "").strip()
        if not text:
            raise LLMEmptyResponseError(
                f"El modelo '{model}' devolvió una respuesta vacía en /api/chat."
            )
        logger.info(
            "Chat completado",
            extra={"extra_data": {"model": model, "duration_ms": duration_ms}},
        )
        return GenerationResult(
            text=text,
            model=model,
            provider=self.name,
            duration_ms=duration_ms,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
        )

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Embeddings vía /api/embed (moderno) con fallback a /api/embeddings.

        Nota MVP: el RAG por defecto usa búsqueda por palabras clave; este
        método queda disponible para el futuro índice vectorial.
        """
        if not texts:
            return []
        try:
            data = self._request(
                "POST", "/api/embed", json_body={"model": model, "input": texts}
            )
            embeddings = data.get("embeddings")
            if isinstance(embeddings, list):
                return [list(map(float, vec)) for vec in embeddings]
            raise LLMInvalidResponseError("Respuesta de /api/embed sin 'embeddings'.")
        except (LLMModelNotFoundError, LLMConnectionError, LLMTimeoutError):
            raise
        except LLMProviderError:
            # API antigua: un texto por petición.
            results: list[list[float]] = []
            for text in texts:
                data = self._request(
                    "POST", "/api/embeddings", json_body={"model": model, "prompt": text}
                )
                embedding = data.get("embedding")
                if not isinstance(embedding, list):
                    raise LLMInvalidResponseError(
                        "Respuesta de /api/embeddings sin 'embedding'."
                    )
                results.append(list(map(float, embedding)))
            return results
