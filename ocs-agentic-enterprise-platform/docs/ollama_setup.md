# Configuración de Ollama

La plataforma usa la API local de Ollama como proveedor de IA. Todo ocurre en tu máquina:
ningún dato sale a Internet.

## Instalación

- **Windows / macOS**: instalador oficial en <https://ollama.com/download>
- **Linux**:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

## Arranque

```bash
ollama serve
```

Por defecto escucha en `http://localhost:11434` (configurable con `OLLAMA_BASE_URL` en `.env`).
En Windows/macOS la app de escritorio arranca el servidor automáticamente.

## Modelos recomendados

```bash
ollama pull llama3.1:8b      # generalista por defecto de la plataforma
ollama pull qwen2.5:7b       # buen rendimiento multilingüe (ES)
ollama pull mistral          # ligero y rápido
ollama pull deepseek-coder   # tareas relacionadas con código
ollama pull nomic-embed-text # embeddings (para el RAG vectorial del roadmap)
```

Orientación de recursos (cuantización por defecto de Ollama):

| Modelo | RAM aproximada | Uso |
|---|---|---|
| `llama3.1:8b` | ~6-8 GB | Equilibrio calidad/velocidad |
| `qwen2.5:7b` | ~6 GB | Español muy sólido |
| `mistral` | ~5 GB | Respuestas rápidas |
| `deepseek-coder` | ~5 GB | Código |

## Endpoints que usa la plataforma

| Endpoint | Uso en la plataforma |
|---|---|
| `GET /api/tags` | `list_models()`, healthcheck y verificación de modelo descargado |
| `POST /api/generate` | Clasificación de intención con LLM y `/models/test` |
| `POST /api/chat` | Ejecución de agentes (system + user) |
| `POST /api/show` | `get_model_info()` |
| `POST /api/embed` (fallback `/api/embeddings`) | `embed()` — preparado para el RAG vectorial |

## Variables de entorno relevantes

```env
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_OLLAMA_MODEL=llama3.1:8b
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_TIMEOUT=120
```

## Comprobación

```bash
curl http://localhost:8000/health/ollama
```

Respuesta esperada con todo correcto:

```json
{"status": "up", "models_available": 3, "default_model": "llama3.1:8b", "default_model_available": true}
```

## Manejo de errores (qué verás si algo falla)

| Situación | Comportamiento de la plataforma |
|---|---|
| Ollama no levantado | Ejecución `failed` con mensaje "Ejecuta `ollama serve`"; `/health/ollama` en `down` |
| Modelo no descargado | Mensaje con la lista de modelos instalados y el comando `ollama pull <modelo>` |
| Timeout | Mensaje sugiriendo modelo más pequeño o subir `OLLAMA_TIMEOUT` |
| Respuesta vacía / JSON inválido | Error explícito del proveedor, ejecución `failed` auditada |

## Consejos

- Primer arranque de un modelo: Ollama lo carga en memoria (puede tardar >30 s).
- Si usas CPU sin GPU, empieza con `mistral` y sube de tamaño según latencia tolerable.
- `ollama list` muestra los modelos descargados; `ollama rm <modelo>` libera espacio.
