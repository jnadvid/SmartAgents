# Equipos multi-agente (Squads)

Un **squad** es un equipo de agentes que colabora sobre una **misma tarea**. El modo de
ejecución es **pipeline** (en cadena): cada agente recibe la tarea original más el trabajo
acumulado de los agentes anteriores, de modo que el resultado se va refinando.

Todo el trabajo del equipo queda en **una única ejecución auditable** (`AgentExecution`), con
pasos `squad_selection` (selección del equipo) y un `agent_run` por cada agente en el
Chain-of-Work. La verificación y la confianza se calculan sobre el resultado combinado.

## Equipos predefinidos

| Squad | Área | Cadena de agentes |
|---|---|---|
| `dev_team` | programming | architect → backend → frontend → code_reviewer → qa |
| `secure_dev_team` | programming | architect → backend → appsec → code_reviewer → qa |
| `code_review_squad` | programming | code_reviewer → appsec → qa |
| `incident_response_team` | cybersecurity | incident_responder → threat_intel → compliance → report |
| `product_launch_team` | business | market_research → strategy → sales_proposal → project_manager |
| `compliance_audit_team` | compliance | compliance → dpo → document_audit → report |
| `people_team` | hr | recruiter → people_ops → org_psychologist |
| `data_initiative_team` | data | data_analyst → strategy → report |

Catálogo en vivo: `GET /agents/squads`.

## Equipos ad-hoc

Puedes componer un equipo a medida indicando una lista ordenada de **2 o más** agentes
(`agent_names`). El orden importa: define el orden de la cadena.

## API

```http
POST /agents/squads/execute
{
  "task": "Implementa y prueba un endpoint de login",
  "squad_name": "dev_team",          // o bien:
  "agent_names": ["backend_developer", "code_reviewer", "qa_test_engineer"],
  "model": null,
  "use_documents": false,
  "extra_context": "```python\n# código de partida\n```"
}
```

La respuesta es una `ExecutionResponse` estándar: `agent_name` será `squad:<nombre>` (o
`squad:custom`), `auxiliary_agents` lista los miembros y `final_output` concatena las
secciones de cada agente.

## Cómo añadir un squad predefinido

1. Añade un `Squad(...)` a `DEFAULT_SQUADS` en `backend/app/agents/squads.py` con miembros
   que existan en el registro de agentes.
2. (Opcional) Añade un test que valide `validate_against(agent_registry)`.

## Límites y notas

- Máximo de miembros por ejecución: 8 (constante `_MAX_SQUAD_MEMBERS`).
- El contexto que se pasa a cada agente se trunca para no exceder el tamaño del prompt.
- La ejecución es **secuencial** (no paralela): la latencia es la suma de la de cada agente.
- Si un agente falla por error del LLM, la ejecución se marca `failed` y queda auditada.
