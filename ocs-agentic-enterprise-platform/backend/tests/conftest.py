"""Fixtures compartidas de los tests.

Importante: las variables de entorno se fijan ANTES de importar `app.*`
para que la configuración cacheada sea determinista en los tests.
"""
from __future__ import annotations

import os

os.environ.setdefault("USE_LLM_INTENT_FALLBACK", "false")
os.environ.setdefault("ENABLE_AUXILIARY_AGENTS", "false")
os.environ.setdefault("ENABLE_AUTH", "false")
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("ENABLE_SCHEDULER", "false")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.registry import AgentRegistry, build_default_registry as build_agents
from app.database import Base
from app.llm.base import (
    BaseLLMProvider,
    ChatMessage,
    GenerationResult,
    LLMConnectionError,
    ModelInfo,
    ProviderHealth,
)
from app.tools.registry import ToolRegistry, build_default_registry as build_tools

FAKE_MODEL = "fake-model"


class FakeLLMProvider(BaseLLMProvider):
    """Proveedor LLM determinista para tests (sin red).

    El chat responde con las secciones Markdown exigidas en el prompt del
    agente, de modo que el verificador y el scorer trabajen con una salida
    realista.
    """

    name = "fake"

    def __init__(self) -> None:
        self.chat_calls: list[list[ChatMessage]] = []
        self.generate_calls: list[str] = []

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(status="up", base_url="fake://local", models_available=2)

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(name=FAKE_MODEL), ModelInfo(name="llama3.1:8b")]

    def get_model_info(self, model: str) -> ModelInfo:
        return ModelInfo(name=model)

    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        self.generate_calls.append(prompt)
        return GenerationResult(text="OK", model=model, provider=self.name, duration_ms=1)

    def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        self.chat_calls.append(messages)
        user_content = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        sections = self._extract_sections(user_content)
        if not sections:
            sections = ["Resumen", "Recomendaciones", "Incertidumbre y límites", "Confianza"]
        parts: list[str] = []
        for section in sections:
            parts.append(f"## {section}")
            if "incertidumbre" in section.lower():
                parts.append("Declaro incertidumbre: faltan datos de contexto para afinar el análisis.")
            elif "confianza" in section.lower():
                parts.append("Media: salida de prueba generada por el proveedor fake.")
            else:
                parts.append(f"Contenido de prueba para la sección {section}.")
            parts.append("")
        return GenerationResult(
            text="\n".join(parts).strip(), model=model, provider=self.name, duration_ms=5
        )

    @staticmethod
    def _extract_sections(user_content: str) -> list[str]:
        sections: list[str] = []
        capture = False
        for line in user_content.splitlines():
            if "FORMATO DE SALIDA REQUERIDO" in line:
                capture = True
                continue
            if capture and line.startswith("## "):
                sections.append(line.removeprefix("## ").strip())
        return sections


class DownLLMProvider(FakeLLMProvider):
    """Simula Ollama caído: cualquier generación falla."""

    name = "down"

    def chat(self, messages, model, temperature: float = 0.2, max_tokens=None):  # type: ignore[override]
        raise LLMConnectionError("No se puede conectar con Ollama (simulado).")


@pytest.fixture(autouse=True)
def _reset_runtime_config():
    """Aísla el overlay de ajustes en runtime entre tests."""
    from app import runtime_config

    runtime_config.reset()
    yield
    runtime_config.reset()


@pytest.fixture()
def memory_session_factory():
    """Motor SQLite en memoria compartido entre hilos + tablas creadas."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    from app import models  # noqa: F401 - registra tablas

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    yield factory
    engine.dispose()


@pytest.fixture()
def db_session(memory_session_factory) -> Session:
    session = memory_session_factory()
    yield session
    session.close()


@pytest.fixture()
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture()
def down_llm() -> DownLLMProvider:
    return DownLLMProvider()


@pytest.fixture(scope="session")
def tool_registry() -> ToolRegistry:
    return build_tools()


@pytest.fixture(scope="session")
def agent_registry() -> AgentRegistry:
    return build_agents()
