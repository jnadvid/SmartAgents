# OCS Agentic Enterprise Platform

Plataforma **local** de agentes de IA multifuncionales, **auditables y extensibles** para
tareas empresariales. Sin Docker, sin PostgreSQL, sin Redis y sin dependencias cloud:
solo **Python 3.11+, FastAPI, SQLite y Ollama**.

> Las respuestas de los agentes son orientativas. Los agentes legal, financiero, de
> compliance, protección de datos y bienestar **no sustituyen asesoría profesional**
> (jurídica, financiera o clínica) y lo declaran en cada respuesta.

## Novedades de la Fase 3

- 🧑‍💼 **36 agentes especializados divididos por áreas**: Programación (8), Ciberseguridad (6),
  Negocio (3), RRHH (3), Psicología (3), Compliance (2), Proyectos (2), además de datos,
  documentos, ventas, finanzas, legal, investigación, soporte e informes.
- 💻 **Área de Programación** con herramientas deterministas de **análisis estático de código**
  (estructura, calidad, SAST/CWE, esqueletos de test, TODOs) — los agentes *interactúan* con
  el código que pegas **sin ejecutarlo nunca**.
- 👥 **Equipos (squads) multi-agente**: varios agentes colaboran **en cadena** sobre una misma
  tarea (p. ej. *arquitecto → backend → frontend → revisor → QA*). Equipos predefinidos o
  ad-hoc, todo en **una única ejecución auditable**.
- ⏰ **Programador de tareas**: lanza tareas a un agente, un equipo o en modo auto de forma
  **puntual o periódica** (una vez, cada X minutos, diaria, semanal o **cron**), con zona
  horaria. Hilo local en proceso, sin Celery ni cron del sistema.
- 🛡️ **Equipos de seguridad** (blue/red/purple team, SOC, ciberseguridad industrial OT) y
  **psicología de la ciberseguridad**, con **conectores de datos** (Wazuh, JSON/CSV) y
  **acceso de lectura definido por agente** para automatizar, p. ej., el **bucle del SOC**
  (leer Wazuh → investigar → el jefe de SOC decide derivación y conclusión). Ver
  [`docs/use_cases.md`](docs/use_cases.md).

## Novedades de la Fase 2

- 📊 **Dashboard visual** con KPIs, gráficos (por agente, intención, herramientas, estado)
  y línea de actividad de los últimos 14 días.
- 🧠 **RAG semántico**: embeddings locales con Ollama (`nomic-embed-text`) guardados en
  SQLite y **búsqueda híbrida** (palabras clave + similitud coseno), con degradación
  elegante a keyword si Ollama no está disponible.
- ⬇️ **Exportación** de cualquier ejecución a **Markdown o HTML** (informe autocontenido).
- 🎛️ **Interfaz rediseñada** con navegación lateral, anillo de confianza y Chain-of-Work
  como línea de tiempo.
- 🪟 **`OCS-Platform.bat`**: script todo-en-uno para Windows que instala, prepara Ollama,
  arranca, detiene y gestiona la plataforma desde un menú.

---

## ¿Qué es?

Una plataforma donde introduces una tarea en lenguaje natural y el sistema:

1. Clasifica la **intención** (16 categorías) con reglas y, opcionalmente, con el propio LLM.
2. Selecciona el **agente** adecuado (o usas el modo manual).
3. El agente genera un **plan auditable**, ejecuta **herramientas deterministas locales**
   (solo las autorizadas) y consulta a **Ollama**.
4. La respuesta pasa por un **verificador** y se calcula una **confianza** explicable.
5. Todo queda registrado en SQLite como **Chain-of-Work**: qué se decidió, qué evidencia
   se usó y qué riesgos se detectaron — sin guardar el razonamiento literal del modelo.

### Casos de uso generales

- Redacción de políticas, procedimientos, emails e informes.
- Análisis de datos pegados (CSV/tablas) con estadísticas y anomalías.
- Propuestas comerciales, investigación de mercado, planes de proyecto.
- Revisión orientativa de contratos, análisis financiero básico.
- Respuestas a clientes, planes de formación, informes ejecutivos.

### Casos de uso de programación

- Diseño de arquitectura (ADR, trade-offs), implementación backend/frontend.
- Revisión de código (calidad, complejidad), generación de tests y documentación técnica.
- Diseño de esquemas de BD y revisión de SQL; CI/CD e infraestructura como código.
- Equipo de desarrollo completo en cadena (arquitecto → dev → revisor → QA).

### Casos de uso de psicología y personas

- Psicología organizacional (clima, motivación, gestión del cambio).
- Psicología de UX (carga cognitiva, persuasión ética, accesibilidad cognitiva).
- Bienestar laboral y prevención del burnout (orientación general, no clínica).
- Selección de talento y People Ops (desempeño, políticas, retención).

### Casos de uso de ciberseguridad

- **Bucle del SOC automatizado**: leer alertas de Wazuh cada X → Blue Team investiga →
  threat hunter caza → el **jefe de SOC** decide derivación y conclusión (squad + scheduler).
- Blue / Red / Purple Team: investigación, emulación de adversario autorizada (sin payloads),
  matriz de cobertura y gaps de detección; ingeniería de detección (Sigma).
- **Ciberseguridad industrial (OT/ICS)**: Purdue, IEC 62443, recomendaciones safety-first.
- **Psicología de la ciberseguridad**: factor humano, ingeniería social y concienciación.
- Análisis de alertas Wazuh/SIEM con normalización y mapeo MITRE ATT&CK heurístico.
- Triaje de vulnerabilidades (CVSS + criticidad + exposición → prioridad P1-P4 y SLA).
- Gap analysis simplificado contra ISO 27001 / RGPD.
- Detección defensiva de patrones de prompt injection y recomendaciones de hardening.

---

## Arquitectura

```
Usuario (frontend HTML/JS)
        │
        ▼
FastAPI (backend/app/api)
        │
        ▼
AgentRunner ──► ExecutionEngine
                │  1. IntentClassifier (reglas + LLM opcional)
                │  2. TaskRouter (intención → agente + auxiliares)
                │  3. AgentPlanner (plan auditable)
                │  4. RAG opcional (chunks en SQLite)
                │  5. Agente (herramientas autorizadas + Ollama)
                │  6. ResponseVerifier (validación)
                │  7. ConfidenceScorer (confianza explicable)
                │
                ├──► ToolRegistry (19 herramientas deterministas)
                ├──► OllamaProvider (http://localhost:11434)
                └──► ChainOfWorkRecorder ──► SQLite (auditoría completa)
```

- **44 agentes** especializados en 16 áreas (programación, ciberseguridad —incl. blue/red/
  purple team, SOC y OT—, negocio, RRHH, psicología, compliance, proyectos, datos, etc.).
- **12 equipos (squads)** predefinidos + equipos ad-hoc para ejecución multi-agente en cadena.
- **Conectores de datos** (Wazuh, JSON/CSV local, HTTP opt-in) con **acceso de lectura
  definido por agente** (`data_access`): leen fuentes reales para actuar en automático.
- **Programador de tareas** local (puntual/periódico) que puede **leer un conector antes de
  ejecutar** (p. ej. el bucle del SOC).
- **24 herramientas** deterministas: sin Internet, sin comandos del sistema, con validación
  Pydantic, timeout y log de auditoría. Solo acceden a datos vía la BD local (`backend/data`).
- Detalle en [`docs/architecture.md`](docs/architecture.md), [`docs/squads.md`](docs/squads.md),
  [`docs/scheduler.md`](docs/scheduler.md), [`docs/connectors.md`](docs/connectors.md) y
  [`docs/use_cases.md`](docs/use_cases.md).

## Requisitos

- Python **3.11 o superior**
- [Ollama](https://ollama.com) instalado en local
- ~8 GB de RAM para modelos 7B-8B (cuantizados)

## Instalación

### Windows

```bat
git clone <este-repositorio>
cd ocs-agentic-enterprise-platform

python -m venv .venv
.venv\Scripts\activate

pip install -r backend\requirements.txt
copy .env.example .env
```

### Linux / macOS

```bash
git clone <este-repositorio>
cd ocs-agentic-enterprise-platform

python3 -m venv .venv
source .venv/bin/activate

pip install -r backend/requirements.txt
cp .env.example .env
```

### Instalación de Ollama

- **Windows / macOS**: descarga el instalador desde <https://ollama.com/download>.
- **Linux**: `curl -fsSL https://ollama.com/install.sh | sh`

Arranca el servidor de Ollama (queda escuchando en `http://localhost:11434`):

```bash
ollama serve
```

### Modelos recomendados

```bash
ollama pull llama3.1:8b      # generalista por defecto
ollama pull qwen2.5:7b       # alternativa multilingüe
ollama pull mistral          # rápido y ligero
ollama pull deepseek-coder   # tareas con código
ollama pull nomic-embed-text # embeddings (RAG vectorial futuro)
```

Guía completa en [`docs/ollama_setup.md`](docs/ollama_setup.md).

## Ejecución

### Opción A — Windows, script todo-en-uno (recomendada)

Haz doble clic en **`OCS-Platform.bat`** (o ejecútalo desde la consola). Aparece un menú:

```
[1] Instalacion completa (venv + dependencias + .env + BD)
[2] Preparar Ollama (arrancar servidor + descargar modelo)
[3] INICIAR plataforma (backend + navegador)
[4] Detener plataforma
[5] Estado del sistema
[6] Ejecutar tests
[7] Reindexar embeddings (RAG semantico)
[8] Abrir navegador
[9] Inicio rapido (instalar + Ollama + iniciar)
```

La opción **[9] Inicio rápido** hace todo de una vez. Para el día a día: **[3]** para
arrancar y **[4]** para detener.

### Opción B — manual (Windows / Linux / macOS)

```bash
# 1. Inicializar (o migrar) la base de datos SQLite
python backend/app/database.py

# 2. Lanzar el backend (sirve también el frontend)
python run_backend.py

# 3. Abrir en el navegador
#    http://localhost:8000        → interfaz
#    http://localhost:8000/docs   → API interactiva (OpenAPI)
```

## Uso

### Modo auto

1. Pestaña **Asistente** → modo **Auto**.
2. Escribe la tarea (ej.: *"Analiza esta alerta Wazuh"*, *"Hazme una propuesta comercial"*).
3. Opcional: pega datos/alerta/contrato en **Contexto adicional**, marca **RAG** si quieres
   usar tus documentos subidos.
4. **Previsualizar enrutado** muestra intención y agente sin ejecutar; **Ejecutar** lanza la tarea.

### Modo manual

Selecciona modo **Manual**, elige el agente del desplegable (se muestran su descripción y
herramientas autorizadas) y ejecuta. La intención detectada se registra igualmente como metadato.

### Modo equipo (multi-agente)

En el Asistente, elige el modo **👥 Equipo**. Puedes:

- **Equipo predefinido**: selecciona un *squad* (p. ej. *Equipo de Desarrollo*) y sus agentes
  trabajan **en cadena**: cada uno recibe la tarea original más el resultado de los anteriores.
- **Personalizado**: marca los agentes que quieras (2 o más, en orden) y compón tu propio equipo.

El resultado combina el trabajo de todos los agentes en **una única ejecución auditable**, con
pasos `squad_selection` y `agent_run` en el Chain-of-Work. También por API:
`POST /agents/squads/execute` con `squad_name` o `agent_names`.

### Programar tareas (puntuales o periódicas)

En la pestaña **Programador** puedes lanzar una tarea a un agente, un equipo o en modo auto:

- **Periodicidad**: una vez (fecha/hora), cada X minutos, diaria, semanal o **cron** (5 campos),
  con **zona horaria** (p. ej. `Europe/Madrid`).
- **Gestión**: pausar/reanudar, **ejecutar ahora**, ver el **histórico de ejecuciones** y borrar.

Un hilo local comprueba las tareas vencidas cada `SCHEDULER_POLL_SECONDS` y las ejecuta,
reprogramando la siguiente. Cada ejecución queda en el histórico normal (con su Chain-of-Work).
Por API: `POST /scheduler/tasks`. Detalle en [`docs/scheduler.md`](docs/scheduler.md).

### Consultar el Chain-of-Work

- En el resultado de cada ejecución: panel **Chain-of-Work** (línea temporal numerada).
- En la pestaña **Ejecuciones**: histórico completo; botón **Ver** para salida + trazabilidad.
- Por API: `GET /executions/{id}/chain-of-work`.

Qué se guarda (y qué no) está documentado en [`docs/chain_of_work.md`](docs/chain_of_work.md).

### Subir documentos

Pestaña **Documentos** → subir TXT/MD/PDF (máx. 20 MB por defecto). El texto se extrae, se
trocea en chunks y se indexa en SQLite. Después puedes buscar por palabras clave o marcar
**Usar documentos** al ejecutar una tarea para inyectar citas como contexto.

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health`, `/health/ollama` | Estado de la app y de Ollama |
| GET | `/models` · POST `/models/test` | Modelos disponibles / prueba rápida |
| GET | `/agents`, `/agents/categories` | Catálogo de agentes |
| GET | `/agents/squads` | Catálogo de equipos (squads) |
| POST | `/agents/route` | Clasificar intención (sin ejecutar) |
| POST | `/agents/execute` | Ejecutar (auto o manual vía `agent_name`) |
| POST | `/agents/{agent}/execute` | Ejecutar con agente concreto |
| POST | `/agents/squads/execute` | Ejecutar un equipo (predefinido o ad-hoc) |
| GET/POST | `/scheduler/tasks` | Listar / crear tareas programadas |
| GET/PATCH/DELETE | `/scheduler/tasks/{id}` | Ver / editar / borrar una tarea programada |
| POST | `/scheduler/tasks/{id}/{pause\|resume\|run-now}` | Pausar, reanudar o ejecutar ya |
| GET | `/scheduler/status` | Estado del programador |
| GET | `/connectors`, `/connectors/categories` | Catálogo de conectores de datos |
| POST | `/connectors/{name}/read` | Vista previa de lectura de una fuente |
| GET | `/executions`, `/executions/{id}`, `/executions/{id}/chain-of-work` | Histórico y auditoría |
| GET | `/executions/{id}/export?format=markdown\|html` | Exportar informe de ejecución |
| POST | `/documents/upload` · GET `/documents` · POST `/documents/search` | RAG local (keyword/semantic/hybrid) |
| POST | `/documents/reindex-embeddings` | Regenerar embeddings (RAG semántico) |
| GET | `/metrics/summary` | Datos agregados del dashboard |
| GET | `/tools`, `/tools/categories` | Catálogo de herramientas |

## Cómo añadir un nuevo agente

1. Crea `backend/app/agents/mi_agente_agent.py` heredando de `BaseAgent`: define `name`,
   `category`, `description`, `system_prompt`, `allowed_tools`, `output_format` y, si quieres
   herramientas automáticas, sobrescribe `plan_tools()`.
2. Regístralo en `build_default_registry()` (`backend/app/agents/registry.py`).
3. Si quiere enrutado automático: añade la intención en `intent_classifier.py` (keywords) y el
   mapeo en `task_router.py` (`INTENT_AGENT_MAP`).
4. Añade un test. Guía detallada en [`docs/agents.md`](docs/agents.md).

## Cómo añadir una nueva herramienta

1. Crea la clase en el módulo temático de `backend/app/tools/` heredando de `BaseTool`:
   define `name`, `category`, `description`, `input_schema` (Pydantic), `timeout_seconds`
   y `execute()`. Prohibido: red, subprocesos, archivos fuera de `backend/data`.
2. Regístrala en `build_default_registry()` (`backend/app/tools/registry.py`).
3. Autorízala en los agentes que la necesiten (`allowed_tools`).
4. Añade un test. Guía detallada en [`docs/tools.md`](docs/tools.md).

## Tests

```bash
cd backend
pytest          # 127 tests: provider mockeado, clasificador, router, tools, motor,
                # Chain-of-Work, RAG, métricas, exportación, squads, scheduler y conectores
```

## Seguridad

- Autenticación opcional por API key local (`ENABLE_AUTH=true` + `SECRET_KEY` propio).
- Sanitización y redacción de secretos en auditoría y logs.
- Herramientas en allow-list por agente, validadas y con timeout.
- Detección defensiva de prompt injection.
- Modelo completo en [`docs/security_model.md`](docs/security_model.md).

## Limitaciones (MVP)

- **Sin navegación web**: la investigación de mercado trabaja solo con datos aportados (y lo declara).
- **RAG semántico (Fase 2)** con embeddings de Ollama y búsqueda híbrida sobre SQLite.
  La similitud coseno se calcula en Python (escala local); un índice vectorial dedicado
  (ej. ChromaDB) queda en el roadmap. Si Ollama está caído, cae a búsqueda por palabras clave.
- **Confianza heurística**, no calibrada estadísticamente.
- **PDF**: solo texto extraíble (sin OCR de escaneados).
- **Mono-usuario local**; multiusuario con roles en el roadmap.
- Agentes auxiliares: se **proponen** siempre; su ejecución es opcional
  (`ENABLE_AUXILIARY_AGENTS=true`) por coste de latencia.
- La ejecución es síncrona (HTTP bloqueante); colas/streaming en el roadmap.

## Roadmap

Ver [`docs/roadmap.md`](docs/roadmap.md): RAG vectorial dedicado (ChromaDB), streaming de
tokens, multiusuario con roles, colas de ejecución y notificaciones de tareas programadas.
Ya entregados en la Fase 3: agentes por áreas, equipos multi-agente y programación de tareas.

## Estructura del proyecto

```
ocs-agentic-enterprise-platform/
  backend/
    app/
      main.py · config.py · database.py · models.py · schemas.py
      agents/         # BaseAgent + 44 agentes + squads + registro
      orchestration/  # clasificador, router, planner, motor (+squads), verificador, scorer
      connectors/     # conectores de datos (Wazuh, JSON/CSV, HTTP opt-in) + registro
      llm/            # contrato LLM + OllamaProvider + ModelRouter
      tools/          # BaseTool + 24 herramientas (incl. análisis de código) + registro
      scheduler/      # cálculo de fechas (cron/diaria/…) + hilo del programador
      audit/          # Chain-of-Work
      rag/            # loader, chunker, retriever, embeddings (RAG semántico)
      api/            # routers FastAPI (scheduler, conectores, métricas, exportación…)
      security/       # auth, políticas, sanitización
      services/       # fachadas: agent_runner, scheduler, documentos, ejecuciones, métricas
    scripts/          # seed_use_cases.py (casos de uso de ejemplo)
    data/             # SQLite + documentos + datos de conectores (no versionado)
    tests/            # 127 tests
  examples/           # datos de muestra (alertas Wazuh)
  frontend/           # index.html + app.js + style.css (vanilla, con dashboard)
  docs/               # documentación técnica
  OCS-Platform.bat    # gestor todo-en-uno para Windows
  run_backend.py      # punto de entrada local
  .env.example        # configuración de ejemplo
```
