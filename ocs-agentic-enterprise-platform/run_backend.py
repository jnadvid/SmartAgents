"""Punto de entrada local de la OCS Agentic Enterprise Platform.

Lanza el backend FastAPI con uvicorn sirviendo también el frontend.

Uso:
    python run_backend.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"

# Permite importar el paquete `app` sin instalar nada.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    import uvicorn

    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))

    print("=" * 60)
    print("OCS Agentic Enterprise Platform")
    print(f"Backend + frontend en: http://{host}:{port}")
    print("Documentación de la API: http://%s:%s/docs" % (host, port))
    print("Recuerda tener Ollama levantado: `ollama serve`")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        app_dir=str(BACKEND_DIR),
        reload=False,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
