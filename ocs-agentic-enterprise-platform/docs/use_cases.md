# Casos de uso automatizados

Combinando **conectores** (datos), **equipos** (multi-agente) y el **programador**, los
agentes actúan en automático. El patrón general:

> conector (lee datos cada X) → agente/equipo (investiga) → agente decisor (concluye/deriva)

Arranque rápido de los ejemplos (crea las tareas **pausadas**):

```bash
python backend/scripts/seed_use_cases.py          # crea ejemplos pausados + alertas de muestra
python backend/scripts/seed_use_cases.py --activate # crearlas ya activas
```

---

## ⭐ Caso estrella: bucle del SOC (Blue Team)

Cada 30 minutos se leen las alertas de Wazuh; el **analista Blue Team** las investiga, el
**threat hunter** busca señales adicionales y el **jefe de SOC** decide la derivación y la
conclusión final. Todo en una ejecución auditable.

- **Conector:** `wazuh_alerts` (nivel ≥ 7)
- **Equipo:** `soc_investigation_team` = `blue_team_analyst → threat_hunter → soc_manager`
- **Resultado:** investigación + **decisión de derivación** (a IR, CTI, vulnerabilidades…) y
  **conclusión** (cerrar / contener / escalar). Si no hay alertas, la ejecución se **omite**.

```json
POST /scheduler/tasks
{
  "name": "SOC · Investigación de alertas Wazuh",
  "task": "Investiga las alertas, prioriza, descarta falsos positivos y decide la derivación y la conclusión.",
  "target_kind": "squad",
  "target_ref": "soc_investigation_team",
  "connector": "wazuh_alerts",
  "connector_params": { "min_level": 7, "limit": 50 },
  "schedule_kind": "interval",
  "interval_minutes": 30
}
```

El jefe de SOC (`soc_manager`) emite secciones **Decisión de derivación** y **Conclusión final**.

---

## Un caso de uso por agente

| Agente | Disparador (conector + periodicidad) | Resultado |
|---|---|---|
| **soc_manager** (Jefe de SOC) | `wazuh_alerts`, en el equipo SOC cada 30 min | Prioriza, **deriva** a la cola/equipo correcto y **concluye** |
| **blue_team_analyst** | `wazuh_alerts`, cada 15-30 min | Investigación de alertas, correlación y recomendación de escalado |
| **threat_hunter** | `wazuh_alerts`, diario 07:30 | Hipótesis de caza + lógica de detección sobre los datos del día |
| **detection_engineer** | sin conector, semanal (lunes 09:00) | Nueva regla Sigma/SIEM para una técnica MITRE no cubierta |
| **red_team_operator** | sin conector, a demanda / mensual | Plan de emulación de adversario autorizado (TTPs, sin payloads) |
| **purple_team_lead** | `wazuh_alerts`, tras un ejercicio | Matriz de cobertura técnica→detección y gaps priorizados |
| **ot_security_analyst** | `local_json`/`local_csv` (inventario OT), mensual | Evaluación OT (Purdue/IEC 62443) compatible con la operación |
| **cyberpsychology_analyst** | `local_csv` (resultados de phishing), mensual | Análisis del factor humano e intervenciones de concienciación |

### Ejemplos de payload

Threat hunting diario sobre Wazuh:

```json
{ "name": "Threat hunting diario", "task": "Caza de amenazas sobre las alertas recientes.",
  "target_kind": "agent", "target_ref": "threat_hunter",
  "connector": "wazuh_alerts", "connector_params": { "min_level": 5, "limit": 100 },
  "schedule_kind": "daily", "time_of_day": "07:30", "timezone": "Europe/Madrid" }
```

Concienciación a partir de una simulación de phishing (CSV en `data/connectors`):

```json
{ "name": "Análisis de phishing mensual", "task": "Analiza los resultados de la simulación y propón intervenciones.",
  "target_kind": "agent", "target_ref": "cyberpsychology_analyst",
  "connector": "local_csv", "connector_params": { "path": "phishing/resultados.csv" },
  "schedule_kind": "cron", "cron": "0 9 1 * *", "timezone": "Europe/Madrid" }
```

Evaluación OT a partir de un inventario de activos (JSON en `data/connectors`):

```json
{ "name": "Evaluación OT trimestral", "task": "Evalúa la seguridad del entorno OT del inventario.",
  "target_kind": "squad", "target_ref": "ot_security_assessment",
  "connector": "local_json", "connector_params": { "path": "ot/inventario.json" },
  "schedule_kind": "cron", "cron": "0 8 1 1,4,7,10 *", "timezone": "Europe/Madrid" }
```

---

## Casos de uso de negocio/programación (mismo patrón)

El patrón vale para cualquier área:

- **Resumen de KPIs semanal:** `local_csv` (export de ventas) → `data_initiative_team` (analista
  → estrategia → informe), lunes 08:00.
- **Revisión de código nocturna:** pega el diff en `extra_context` o usa `local_json` → squad
  `code_review_squad`, cron diario.
- **Informe de cumplimiento mensual:** `local_json` (controles) → `compliance_audit_team`.

> Recuerda: si una tarea usa un conector, el agente/equipo objetivo debe tener ese conector en
> su `data_access`. Revisa el acceso de cada agente en la pestaña **Agentes**.
