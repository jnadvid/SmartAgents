# Herramientas

Las herramientas son **deterministas y locales**: producen evidencia verificable
(estadísticas, parseos, detecciones por patrones, esqueletos estructurados) que el agente
cita en su respuesta. No usan el LLM, ni la red, ni el sistema de archivos fuera de
`backend/data`.

## Contrato (`BaseTool`)

- `name`, `category`, `description`, `required_role`, `timeout_seconds`
- `input_schema`: modelo Pydantic (validación estricta de la entrada)
- `execute(payload, ctx) -> dict`: lógica pura
- `run(raw_input, ctx) -> ToolResult`: punto de entrada controlado — valida, ejecuta con
  timeout en hilo dedicado y devuelve siempre `ToolResult` (`success`/`error`/`timeout`/`denied`)

El `ToolRegistry` aplica la **allow-list del agente** y es la única vía de invocación.

## Catálogo (24)

### Documentales
| Herramienta | Qué hace |
|---|---|
| `summarize_text` | Resumen extractivo (frases literales mejor puntuadas), keywords y métricas |
| `extract_action_items` | Acciones pendientes (TODO, casillas, imperativos) con línea de origen |
| `search_documents` | Búsqueda por keywords en los chunks de SQLite, con citas |
| `summarize_document` | Resumen extractivo de un documento subido (por id) |
| `compare_documents` | Similitud aproximada, keywords comunes/exclusivas, tamaños |

### Datos y negocio
| Herramienta | Qué hace |
|---|---|
| `analyze_table_text` | Parsea CSV/TSV/tabla Markdown: stats por columna, faltantes, outliers (IQR) |
| `extract_risks` | Frases con indicadores de riesgo clasificadas (high/medium/low) |
| `classify_customer_request` | Categoría de la consulta, urgencia y tono |

### Ventas, finanzas, legal, proyectos
| Herramienta | Qué hace |
|---|---|
| `create_sales_proposal` | Esqueleto de propuesta (9 secciones) + campos faltantes + checklist |
| `calculate_basic_financials` | Extrae cifras etiquetadas y calcula margen, break-even y escenarios ±10% |
| `review_contract_text` | Cláusulas, 11 patrones de riesgo contractual, obligaciones, ambigüedades |
| `create_project_plan` | Fases con reparto temporal, hitos y riesgos genéricos |

### Informes
| Herramienta | Qué hace |
|---|---|
| `generate_markdown_report` | Compone Markdown a partir de título y secciones (TOC opcional) |
| `generate_executive_report` | Informe ejecutivo con hallazgos ordenados por severidad |

### Ciberseguridad / compliance / prompt security
| Herramienta | Qué hace |
|---|---|
| `parse_wazuh_alert` | Normaliza alertas Wazuh JSON (regla, nivel→severidad, MITRE, agente, IPs) |
| `map_to_mitre_attack` | Mapeo heurístico keywords→técnicas MITRE ATT&CK (subconjunto, declara cobertura parcial) |
| `calculate_cvss_priority` | CVSS × criticidad × exposición × exploit → P1-P4 + SLA + justificación |
| `generate_compliance_gap` | Gap analysis contra subconjunto ISO 27001:2022 / RGPD: cobertura % y brechas |
| `check_prompt_injection_patterns` | Detección defensiva de 9 familias de inyección + mitigaciones |

### Programación (análisis estático, **sin ejecutar** el código)
| Herramienta | Qué hace |
|---|---|
| `analyze_code_structure` | Funciones, clases, imports, complejidad ciclomática y métricas (AST en Python; heurística en otros lenguajes) |
| `review_code_quality` | Hallazgos de calidad con línea/severidad: funciones largas, exceso de argumentos, sin docstring, except desnudo, líneas largas, TODOs |
| `scan_code_security` | SAST heurístico con CWE: eval/exec, inyección de comandos/SQL, deserialización insegura, hash débil, TLS sin verificar, secretos embebidos |
| `generate_test_skeleton` | Esqueletos de tests (pytest/unittest) para las funciones públicas de un módulo Python |
| `extract_code_todos` | Marcadores TODO/FIXME/HACK/XXX/BUG con línea y agrupados por tipo |

## Reglas de seguridad (obligatorias para toda herramienta)

1. Ningún agente puede usar herramientas fuera de su `allowed_tools` (deny + auditoría).
2. Entrada validada con Pydantic (longitudes, rangos, patrones).
3. Toda ejecución queda en `tool_logs` y como paso del Chain-of-Work.
4. Timeout configurado por herramienta.
5. **Prohibido**: comandos del sistema, acceso a Internet, leer/escribir fuera de
   `backend/data` (las documentales acceden solo vía BD).

## Cómo añadir una herramienta

```python
# backend/app/tools/data_tools.py (o el módulo temático que corresponda)
from typing import Any
from pydantic import BaseModel, Field
from app.tools.base import BaseTool, ToolContext


class CountWordsInput(BaseModel):
    text: str = Field(min_length=1, max_length=100000)


class CountWordsTool(BaseTool):
    name = "count_words"
    category = "data"
    description = "Cuenta palabras y caracteres de un texto."
    input_schema = CountWordsInput
    timeout_seconds = 5

    def execute(self, payload: CountWordsInput, ctx: ToolContext) -> dict[str, Any]:
        return {"words": len(payload.text.split()), "chars": len(payload.text)}
```

1. Regístrala en `build_default_registry()` (`tools/registry.py`).
2. Añádela al `allowed_tools` de los agentes que deban usarla.
3. Si necesita BD, usa `ctx.db_session_factory` (nunca rutas de archivo directas).
4. Test en `tests/test_general_tools.py` (o el módulo que corresponda).
