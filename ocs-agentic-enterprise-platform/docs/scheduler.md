# Programador de tareas (Scheduler)

Permite ejecutar tareas de forma **puntual o periódica**, dirigidas a un agente, un equipo
(squad o ad-hoc) o en **modo auto** (lo decide el router). Es 100% local: un hilo en segundo
plano dentro del proceso de FastAPI y **SQLite como única fuente de verdad**. Sin Celery, sin
Redis y sin el cron del sistema operativo.

## Cómo funciona

- Cada tarea guarda su **próxima ejecución** (`next_run_at`, en UTC).
- El hilo del programador se despierta cada `SCHEDULER_POLL_SECONDS` (por defecto 30 s), busca
  las tareas vencidas (`enabled` y `next_run_at <= ahora`), las ejecuta y **reprograma** la
  siguiente. Cada activación crea una ejecución normal (con su Chain-of-Work) y un registro en
  el histórico de la tarea (`ScheduledRun`).
- Si el LLM (Ollama) está caído, la ejecución se marca `failed` y se reprograma igualmente.
- Las tareas `once` se desactivan (`finished`) tras ejecutarse una vez.

Se activa con `ENABLE_SCHEDULER=true` (por defecto). El hilo se arranca en el *lifespan* de la
app y se detiene limpiamente al cerrar.

## Tipos de periodicidad

| `schedule_kind` | Campos | Ejemplo |
|---|---|---|
| `once` | `run_at` (ISO 8601) | una sola vez el 2026-06-20 08:00 |
| `interval` | `interval_minutes` (≥1) | cada 60 minutos |
| `daily` | `time_of_day` (HH:MM) | cada día a las 08:30 |
| `weekly` | `day_of_week` (0=lunes…6=domingo) + `time_of_day` | cada lunes a las 09:00 |
| `cron` | `cron` (5 campos) | `0 9 * * 1` (lunes 09:00) |

Todas las modalidades aceptan `timezone` (IANA, p. ej. `Europe/Madrid`; por defecto `UTC`).
El cálculo de la siguiente ejecución se hace en esa zona y se almacena en UTC.

### Formato cron

Cinco campos: `minuto hora día-del-mes mes día-de-semana`. Soporta `*`, listas (`1,15`),
rangos (`1-5`) y pasos (`*/15`, `1-5/2`). En `día-de-semana`, `0` y `7` son domingo. Si se
restringen a la vez día-del-mes y día-de-semana, se aplica la semántica **OR** de crontab.

## Objetivos (`target_kind`)

- `auto`: lo decide el router según la intención.
- `agent`: un agente concreto (`target_ref` = nombre del agente).
- `squad`: un equipo predefinido (`target_ref` = nombre del squad).
- `team`: equipo ad-hoc (`agent_names` = lista de 2+ agentes).

## API

```http
POST   /scheduler/tasks                 # crear
GET    /scheduler/tasks                  # listar (?enabled=true|false)
GET    /scheduler/tasks/{id}             # detalle + histórico de runs
PATCH  /scheduler/tasks/{id}             # editar (recalcula la próxima ejecución)
POST   /scheduler/tasks/{id}/pause       # pausar
POST   /scheduler/tasks/{id}/resume      # reanudar
POST   /scheduler/tasks/{id}/run-now     # ejecutar inmediatamente (síncrono)
DELETE /scheduler/tasks/{id}             # borrar
GET    /scheduler/status                 # estado del programador
```

Ejemplo de creación (informe semanal con un equipo, los lunes a las 8:00 de Madrid):

```json
{
  "name": "Informe de seguridad semanal",
  "task": "Resume el estado de seguridad de la semana y prioriza acciones",
  "target_kind": "squad",
  "target_ref": "incident_response_team",
  "schedule_kind": "weekly",
  "day_of_week": 0,
  "time_of_day": "08:00",
  "timezone": "Europe/Madrid"
}
```

## Configuración

| Variable | Por defecto | Descripción |
|---|---|---|
| `ENABLE_SCHEDULER` | `true` | Arranca el hilo del programador |
| `SCHEDULER_POLL_SECONDS` | `30` | Cada cuánto se comprueban las tareas vencidas |

## Límites y notas

- Como máximo se procesan 25 tareas por ciclo (evita avalanchas tras una pausa larga).
- Mono-proceso: pensado para un despliegue local. En multi-worker habría que coordinar el hilo.
- Las marcas de tiempo se guardan en UTC; la zona horaria solo afecta al cálculo de `daily`,
  `weekly` y `cron`.
