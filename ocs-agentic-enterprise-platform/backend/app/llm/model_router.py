"""Selección del modelo Ollama a usar en cada ejecución.

Prioridad: modelo pedido por el usuario > modelo por defecto del agente >
modelo por defecto global (.env). Verifica disponibilidad contra /api/tags
con una pequeña caché para no castigar a Ollama en cada petición.
"""
from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.llm.base import BaseLLMProvider, LLMModelNotFoundError, LLMProviderError

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 15.0


class ModelRouter:
    """Resuelve qué modelo usar y valida que esté disponible."""

    def __init__(self, provider: BaseLLMProvider) -> None:
        self.provider = provider
        self._cached_names: set[str] = set()
        self._cached_at: float = 0.0

    def _available_models(self) -> set[str]:
        now = time.monotonic()
        if self._cached_names and (now - self._cached_at) < _CACHE_TTL_SECONDS:
            return self._cached_names
        names = {m.name for m in self.provider.list_models()}
        self._cached_names = names
        self._cached_at = now
        return names

    def resolve(
        self,
        requested_model: str | None = None,
        agent_default: str | None = None,
        check_availability: bool = True,
    ) -> str:
        """Devuelve el nombre del modelo a usar.

        Lanza LLMModelNotFoundError con la lista de modelos instalados si el
        modelo elegido no está descargado.
        """
        from app import runtime_config

        settings = get_settings()
        global_default = runtime_config.effective("default_ollama_model", settings.default_ollama_model)
        candidate = requested_model or agent_default or global_default

        if not check_availability:
            return candidate

        try:
            names = self._available_models()
        except LLMModelNotFoundError:
            raise
        except LLMProviderError:
            # Si no podemos listar modelos (p. ej. proveedor caído), dejamos que
            # la llamada de generación falle con su propio error explicativo.
            logger.warning("No se pudo verificar disponibilidad de modelos en Ollama")
            return candidate

        if candidate in names or f"{candidate}:latest" in names:
            return candidate

        installed = ", ".join(sorted(names)) or "ninguno"
        raise LLMModelNotFoundError(
            f"El modelo '{candidate}' no está descargado en Ollama. "
            f"Modelos instalados: {installed}. Usa `ollama pull {candidate}`."
        )
