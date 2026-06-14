"""Configuración central de la plataforma.

Lee variables desde el archivo `.env` en la raíz del proyecto (si existe)
y desde variables de entorno. Sin dependencias cloud: todo es local.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> parents[0]=app, parents[1]=backend, parents[2]=raíz
BACKEND_DIR: Path = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Path = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Ajustes de la aplicación, sobrescribibles vía .env o entorno."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Aplicación
    app_name: str = "OCS Agentic Enterprise Platform"
    app_env: str = "local"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # Base de datos local
    database_url: str = "sqlite:///./backend/data/app.db"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    default_ollama_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout: int = 120

    # Seguridad
    secret_key: str = "change-me"
    enable_auth: bool = False

    # Límites
    max_input_chars: int = 30000
    max_document_size_mb: int = 20

    # Orquestación
    use_llm_intent_fallback: bool = True
    enable_auxiliary_agents: bool = False

    # Programador de tareas (scheduler local)
    enable_scheduler: bool = True
    scheduler_poll_seconds: int = 30

    # Conectores de datos (lectura automática para los agentes)
    # Los conectores de archivo (Wazuh local, JSON, CSV) están siempre disponibles
    # y solo leen dentro de backend/data. Los conectores HTTP están desactivados
    # por defecto y, si se activan, solo permiten hosts de la allow-list.
    enable_http_connectors: bool = False
    http_connector_allowlist: str = ""  # hosts separados por comas (p. ej. "localhost,127.0.0.1")
    connector_max_records: int = 200
    connector_timeout: int = 15
    wazuh_alerts_path: str = ""  # ruta al alerts.json de Wazuh (vacío = data/connectors/wazuh/alerts.json)

    # Herramientas de pentesting (Kali). DESACTIVADAS por defecto: ejecutan binarios
    # reales sobre objetivos autorizados. Solo escanean hosts de la allow-list de
    # alcance y requieren confirmación de autorización en cada ejecución.
    enable_pentest_tools: bool = False
    pentest_scope_allowlist: str = ""  # dominios/IPs/CIDR autorizados (coma-separados)
    pentest_timeout: int = 180  # timeout por herramienta (s)
    pentest_max_output_chars: int = 20000  # truncado de salida por herramienta

    # RAG
    rag_chunk_size: int = 1200
    rag_chunk_overlap: int = 150
    rag_top_k: int = 5
    # RAG semántico (Fase 2): embeddings con Ollama + similitud coseno
    rag_use_embeddings: bool = True
    rag_vector_weight: float = 0.65  # peso del coseno en la búsqueda híbrida (0-1)

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    @property
    def resolved_database_url(self) -> str:
        """URL de SQLite con ruta absoluta respecto a la raíz del proyecto.

        Permite ejecutar la aplicación desde cualquier directorio de trabajo.
        """
        prefix = "sqlite:///"
        url = self.database_url
        if url.startswith(prefix):
            raw_path = url[len(prefix) :]
            if not raw_path.startswith("/") and ":" not in raw_path.split("/")[0]:
                rel = raw_path.removeprefix("./")
                return f"{prefix}{(PROJECT_ROOT / rel).as_posix()}"
        return url

    @property
    def data_dir(self) -> Path:
        return BACKEND_DIR / "data"

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def connectors_dir(self) -> Path:
        return self.data_dir / "connectors"

    @property
    def http_connector_hosts(self) -> set[str]:
        return {h.strip().lower() for h in self.http_connector_allowlist.split(",") if h.strip()}

    @property
    def pentest_scope_entries(self) -> list[str]:
        return [e.strip().lower() for e in self.pentest_scope_allowlist.split(",") if e.strip()]

    @property
    def frontend_dir(self) -> Path:
        return PROJECT_ROOT / "frontend"

    @property
    def max_document_size_bytes(self) -> int:
        return self.max_document_size_mb * 1024 * 1024

    def validate_security(self) -> None:
        """Comprueba la configuración de seguridad antes de arrancar."""
        if self.enable_auth and self.secret_key in ("", "change-me"):
            raise RuntimeError(
                "ENABLE_AUTH=true requiere definir un SECRET_KEY propio en .env "
                "(distinto de 'change-me')."
            )


class JsonLogFormatter(logging.Formatter):
    """Formateador de logs estructurados en JSON (una línea por evento)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_data", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(settings: "Settings | None" = None) -> None:
    """Configura logging estructurado para toda la aplicación."""
    cfg = settings or get_settings()
    root = logging.getLogger()
    root.setLevel(cfg.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    if cfg.log_json:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )

    root.handlers.clear()
    root.addHandler(handler)
    # Reduce ruido de librerías de terceros
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


@lru_cache
def get_settings() -> Settings:
    """Instancia única (cacheada) de configuración."""
    return Settings()
