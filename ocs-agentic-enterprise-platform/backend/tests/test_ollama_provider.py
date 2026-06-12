"""Tests del OllamaProvider con transporte HTTP simulado (sin red)."""
from __future__ import annotations

import json

import httpx
import pytest

from app.llm.base import (
    LLMConnectionError,
    LLMEmptyResponseError,
    LLMInvalidResponseError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMTimeoutError,
)
from app.llm.ollama_provider import OllamaProvider


def make_provider(handler) -> OllamaProvider:
    """Provider cuyo cliente HTTP usa un MockTransport."""
    provider = OllamaProvider(base_url="http://ollama.test", timeout=5)
    transport = httpx.MockTransport(handler)
    provider._client = lambda timeout=None: httpx.Client(  # type: ignore[method-assign]
        base_url=provider.base_url, transport=transport, timeout=timeout or provider.timeout
    )
    return provider


def test_list_models_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "llama3.1:8b", "size": 123, "details": {"family": "llama"}},
                    {"name": "mistral:latest", "size": 456, "details": {}},
                ]
            },
        )

    models = make_provider(handler).list_models()
    assert [m.name for m in models] == ["llama3.1:8b", "mistral:latest"]
    assert models[0].family == "llama"


def test_generate_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "llama3.1:8b"
        assert body["stream"] is False
        assert body["options"]["temperature"] == 0.0
        return httpx.Response(200, json={"response": "Hola", "eval_count": 3})

    result = make_provider(handler).generate("di hola", model="llama3.1:8b", temperature=0.0)
    assert result.text == "Hola"
    assert result.completion_tokens == 3


def test_chat_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "Respuesta"}})

    result = make_provider(handler).chat(
        [{"role": "user", "content": "hola"}], model="llama3.1:8b"
    )
    assert result.text == "Respuesta"


def test_empty_response_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "   "})

    with pytest.raises(LLMEmptyResponseError):
        make_provider(handler).generate("hola", model="llama3.1:8b")


def test_model_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'nope' not found"})

    with pytest.raises(LLMModelNotFoundError):
        make_provider(handler).generate("hola", model="nope")


def test_http_500_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(LLMProviderError):
        make_provider(handler).list_models()


def test_invalid_json_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="esto no es json")

    with pytest.raises(LLMInvalidResponseError):
        make_provider(handler).list_models()


def test_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexión rechazada")

    with pytest.raises(LLMConnectionError):
        make_provider(handler).list_models()


def test_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("demasiado lento")

    with pytest.raises(LLMTimeoutError):
        make_provider(handler).generate("hola", model="llama3.1:8b")


def test_healthcheck_down_does_not_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("apagado")

    health = make_provider(handler).healthcheck()
    assert health.status == "down"
    assert "Ollama" in (health.detail or "")


def test_chat_requires_role_and_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(200, json={})

    with pytest.raises(LLMProviderError):
        make_provider(handler).chat([{"role": "user"}], model="m")  # type: ignore[list-item]
