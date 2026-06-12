"""Contrato base de proveedores LLM y jerarquía de errores.

Diseñado para que añadir otro proveedor local en el futuro solo requiera
implementar `BaseLLMProvider`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class LLMProviderError(Exception):
    """Error genérico del proveedor LLM."""


class LLMConnectionError(LLMProviderError):
    """No se puede conectar con el proveedor (¿está Ollama levantado?)."""


class LLMTimeoutError(LLMProviderError):
    """La petición superó el timeout configurado."""


class LLMModelNotFoundError(LLMProviderError):
    """El modelo solicitado no está descargado/disponible."""


class LLMEmptyResponseError(LLMProviderError):
    """El proveedor devolvió una respuesta vacía."""


class LLMInvalidResponseError(LLMProviderError):
    """El proveedor devolvió una respuesta no parseable (JSON inválido, etc.)."""


@dataclass(frozen=True)
class ModelInfo:
    """Información de un modelo disponible en el proveedor."""

    name: str
    size_bytes: int | None = None
    modified_at: str | None = None
    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationResult:
    """Resultado de una generación o chat."""

    text: str
    model: str
    provider: str
    duration_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(frozen=True)
class ProviderHealth:
    """Estado de salud del proveedor."""

    status: str  # "up" | "down"
    base_url: str
    models_available: int = 0
    detail: str | None = None


ChatMessage = dict[str, str]  # {"role": "system"|"user"|"assistant", "content": str}


class BaseLLMProvider(ABC):
    """Interfaz mínima que debe cumplir cualquier proveedor LLM local."""

    name: str = "base"

    @abstractmethod
    def healthcheck(self) -> ProviderHealth:
        """Comprueba si el proveedor está accesible."""

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """Lista los modelos disponibles localmente."""

    @abstractmethod
    def get_model_info(self, model: str) -> ModelInfo:
        """Devuelve información de un modelo concreto (error si no existe)."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        """Generación de texto a partir de un prompt único."""

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        """Chat multi-mensaje (system/user/assistant)."""

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Embeddings de texto. Opcional: no todos los proveedores lo soportan."""
        raise LLMProviderError(f"El proveedor '{self.name}' no soporta embeddings.")
