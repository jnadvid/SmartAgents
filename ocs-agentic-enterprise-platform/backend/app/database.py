"""Base de datos local SQLite con SQLAlchemy 2.0.

Puede ejecutarse directamente para inicializar o migrar el esquema:

    python backend/app/database.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Iterator

# Permite la ejecución directa del módulo (python backend/app/database.py)
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""


_settings = get_settings()

engine: Engine = create_engine(
    _settings.resolved_database_url,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
    """Activa claves foráneas y WAL para un SQLite local más robusto."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia FastAPI: sesión de base de datos por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea directorios de datos y todas las tablas si no existen."""
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.documents_dir.mkdir(parents=True, exist_ok=True)

    # Importa los modelos para registrar las tablas en la metadata.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info(
        "Base de datos inicializada",
        extra={"extra_data": {"url": settings.resolved_database_url}},
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    init_db()
    print(f"Base de datos lista en: {_settings.resolved_database_url}")
