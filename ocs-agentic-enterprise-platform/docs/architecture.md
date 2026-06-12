# Arquitectura

## Principios de diseño

1. **100% local**: FastAPI + SQLite + Ollama. Sin Docker, sin PostgreSQL, sin Redis,
   sin servicios cloud obligatorios.
2. **Auditable por defecto**: cada ejecución produce un Chain-of-Work persistente con
   decisiones, evidencias y riesgos (nunca el razonamiento literal del modelo).
3. **Separación evidencia/síntesis**: las herramientas son **deterministas** (producen
   evidencia verificable: estadísticas, parseos, detecciones por patrones); el LLM
   **sintetiza** sobre esa evidencia. Esto reduce alucinaciones y hace los resultados citables.
4. **Mínimo acoplamiento**: cada capa depende solo de contratos (ABCs y dataclasses),
   lo que permite cambiar el proveedor LLM, añadir agentes o herramientas sin tocar el motor.
5. **Fallo elegante**: Ollama caído, modelo no descargado o herramienta rota nunca tiran
   la plataforma; quedan reflejados en la ejecución con mensaje accionable.

## Capas

```
api/            routers HTTP (FastAPI) — validación Pydantic, errores 4xx/5xx
services/       fachadas de caso de uso (AgentRunner, documentos, ejecuciones)
orchestration/  IntentClassifier → TaskRouter → AgentPlanner → ExecutionEngine
                → ResponseVerifier → ConfidenceScorer
agents/         BaseAgent (ciclo común) + 16 agentes declarativos
tools/          BaseTool (validación+timeout) + ToolRegistry + 19 herramientas
llm/            BaseLLMProvider (contrato) + OllamaProvider + ModelRouter
rag/            document_loader (TXT/MD/PDF) + chunker + retriever (keywords)
audit/          ChainOfWorkRecorder (pasos + tool logs saneados)
security/       auth opcional, políticas (allow-list, límites), sanitización
models.py       8 tablas SQLite (SQLAlchemy 2.0)
```

## Flujo de una ejecución

1. `POST /agents/execute` valida la entrada (tamaño máximo, agente válido).
2. **IntentClassifier**: reglas por keywords ponderadas (ES/EN, normalizadas sin acentos).
   Si la confianza < 0.55 y `USE_LLM_INTENT_FALLBACK=true`, se pide a Ollama que elija
   una categoría del catálogo cerrado (con parseo defensivo y fallback a reglas).
3. **TaskRouter**: mapa cerrado intención→agente + agentes auxiliares propuestos.
   En modo manual se respeta el agente del usuario y la intención queda como metadato.
4. Se crea `AgentExecution` (status `running`) + `TaskRoute` y se registran los primeros
   pasos del Chain-of-Work.
5. **ModelRouter** resuelve el modelo (usuario > agente > .env) y verifica que esté
   descargado (`/api/tags`, con caché de 15 s).
6. **RAG opcional**: recuperación por keywords sobre los chunks en SQLite; las citas
   (archivo + chunk + score) van al prompt y al Chain-of-Work.
7. **AgentPlanner** construye el plan auditable (objetivo, pasos, herramientas previstas,
   evidencias esperadas, formato de salida).
8. El **agente** ejecuta sus herramientas autorizadas (cada una validada, con timeout y
   registrada en `tool_logs` + paso CoW) y llama a Ollama (`/api/chat`) con un prompt
   estructurado: tarea + contexto + evidencia + formato de secciones exigido.
9. **ResponseVerifier**: comprobaciones duras (vacía, secretos) y blandas (secciones,
   citas fabricadas, incertidumbre, recomendaciones).
10. **Agentes auxiliares** (si `ENABLE_AUXILIARY_AGENTS=true`): añaden notas complementarias.
11. **ConfidenceScorer**: score 0.05-0.95 con desglose por factores (entrada, evidencia,
    verificación, estructura, incertidumbre declarada).
12. La ejecución se cierra (`completed` / `completed_with_warnings` / `failed`) y la API
    devuelve salida + verificación + confianza + Chain-of-Work completo.

## Decisiones técnicas

| Decisión | Motivo |
|---|---|
| SQLAlchemy 2.0 (Mapped/typed) | Type hints reales y migración futura sencilla |
| SQLite WAL + foreign keys | Robustez local sin servidor de BD |
| Endpoints síncronos (`def`) | Las llamadas a Ollama son bloqueantes y largas; FastAPI las ejecuta en threadpool |
| httpx síncrono en OllamaProvider | Simplicidad; el contrato permite versión async futura |
| Herramientas deterministas sin LLM | Evidencia verificable, testeable y sin coste de inferencia |
| Tools con sesión de BD propia | Ejecutan en hilo separado (timeout); no comparten la sesión del request |
| Frontend vanilla servido por FastAPI | Cero build, un solo proceso, un solo puerto |
| Confianza heurística explicable | Mejor un indicador honesto y auditable que una probabilidad falsa |

## Riesgos y limitaciones conocidos

- El timeout de herramientas no mata el hilo (limitación de Python); las herramientas son
  puras y cortas, así que el impacto es marginal y está documentado.
- La clasificación por reglas puede errar en tareas ambiguas; por eso existe el fallback
  LLM, la vista previa de enrutado y el modo manual.
- El RAG por keywords no encuentra sinónimos; el contrato de `embed()` ya está implementado
  para un índice vectorial futuro.
- SQLite es mono-escritor: suficiente para uso local mono-usuario, no para concurrencia alta.
