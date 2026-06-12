# Chain-of-Work

El Chain-of-Work (CoW) es el registro auditable de **qué hizo la plataforma** en cada
ejecución. Es trazabilidad de decisiones y evidencias, **no** una transcripción del
razonamiento del modelo.

## Qué se guarda

- Qué tarea recibió el sistema (resumen saneado y truncado).
- Qué intención se detectó, con qué método (reglas/LLM) y qué keywords coincidieron.
- Qué agente se seleccionó, por qué, y qué auxiliares se propusieron.
- El plan de trabajo resumido (objetivo, pasos, herramientas, evidencias esperadas).
- Cada herramienta usada: entrada resumida, salida resumida, estado, duración.
- Qué documentos/citas se recuperaron (archivo, chunk, score).
- Qué modelo se consultó (nombre, tamaño del prompt, duración) — nunca el prompt íntegro
  con datos sensibles sin sanear.
- Qué validaciones se realizaron y su resultado.
- Qué riesgo se asignó a cada paso (`info`/`low`/`medium`/`high`/`critical`).
- El desglose del cálculo de confianza.
- Errores, con mensaje accionable.

## Qué NO se guarda (por diseño)

- **Chain-of-thought literal** del modelo (razonamiento interno).
- Secretos, API keys, tokens, contraseñas: todo texto pasa por
  `security/sanitization.py` (redacción por patrones + truncado) antes de persistirse.
- Datos sensibles innecesarios: los campos largos se truncan a un máximo fijo.

## Tipos de paso

| step_type | Significado |
|---|---|
| `task_received` | Recepción y métricas de la tarea |
| `intent_classification` | Intención + confianza + método |
| `agent_selection` | Agente elegido + motivo + auxiliares propuestos |
| `work_plan` | Plan auditable del agente |
| `document_retrieval` | Citas RAG recuperadas |
| `tool_call` | Ejecución de una herramienta (motivo + resumen E/S) |
| `llm_call` | Consulta al modelo (modelo, tamaño, herramientas previas) |
| `auxiliary_agent` | Agente auxiliar ejecutado o propuesto |
| `response_verification` | Resultado del verificador |
| `confidence_scoring` | Score + desglose |
| `final_result` | Cierre con métricas |
| `error` | Fallo con mensaje accionable |

## Modelo de datos

Tabla `chain_of_work_steps`: `execution_id`, `step_number` (secuencial), `step_type`,
`title`, `description`, `agent_name`, `tool_name`, `tool_input_summary`,
`tool_output_summary`, `evidence` (JSON resumido), `risk_level`, `created_at`.

Complementada por `tool_logs` (registro plano por herramienta) y `task_routes`
(decisión de enrutado por ejecución).

## Consulta

- Frontend: panel "Chain-of-Work" en cada resultado y en el histórico de ejecuciones.
- API: `GET /executions/{id}/chain-of-work`.
- SQL directo: la BD es un archivo SQLite local (`backend/data/app.db`).

## Ejemplo real (ejecución típica)

1. `task_received` — Recepción de tarea (812 caracteres).
2. `intent_classification` — Intención: `sales_proposal` (reglas, confianza 0.8).
3. `agent_selection` — Agente: `sales_proposal`; auxiliar propuesto: `market_research`.
4. `work_plan` — Objetivo, 4 pasos, herramienta `create_sales_proposal`.
5. `tool_call` — `create_sales_proposal` OK (12 ms), esqueleto con 9 secciones.
6. `llm_call` — Modelo `llama3.1:8b`, prompt de 3.214 caracteres.
7. `response_verification` — Superada (7/7 comprobaciones).
8. `confidence_scoring` — 0.78 (desglose por factores).
9. `final_result` — Completada.
