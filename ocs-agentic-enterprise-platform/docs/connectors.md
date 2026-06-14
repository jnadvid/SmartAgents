# Conectores de datos y acceso de lectura

Los **conectores** permiten que los agentes actúen **en automático** sobre datos reales: un
conector LEE de una fuente (alertas de Wazuh, JSON/CSV local o, opcionalmente, un endpoint
HTTP autorizado) y los datos se inyectan como contexto a un agente o equipo, normalmente
desde una **tarea programada**.

## Acceso de lectura definido (`data_access`)

Cada agente declara **al definirse** a qué conectores puede acceder, mediante la lista
`data_access` (allow-list). Es el equivalente, para datos, de `allowed_tools`:

```python
class BlueTeamAnalystAgent(BaseAgent):
    ...
    data_access = ["wazuh_alerts", "local_json"]   # solo puede leer estas fuentes
```

- El registro de conectores **deniega** cualquier lectura fuera de la `data_access` del agente.
- Al **programar** una tarea con un conector, se valida que **todos** los agentes implicados
  (el agente, o todos los miembros del squad/equipo) tengan acceso a ese conector; si no, la
  creación falla con un error claro.
- El `data_access` de cada agente se muestra en la pestaña **Agentes** y en `GET /agents`.

## Modelo de seguridad

- **Solo lectura.** Los conectores nunca escriben ni ejecutan nada.
- Los conectores de archivo solo leen dentro de `backend/data/connectors` (protección contra
  path traversal). La única excepción es la ruta del `alerts.json` de Wazuh, que el operador
  puede fijar explícitamente por configuración (`WAZUH_ALERTS_PATH`).
- Los conectores **HTTP están desactivados por defecto**. Si se activan
  (`ENABLE_HTTP_CONNECTORS=true`), solo permiten hosts de `HTTP_CONNECTOR_ALLOWLIST` y no
  siguen redirecciones.
- Toda lectura se sanea/redacta antes de inyectarse como contexto o registrarse.

## Conectores disponibles

| Conector | Lee | Notas |
|---|---|---|
| `wazuh_alerts` | `alerts.json` de Wazuh (NDJSON o array) | Normaliza regla, nivel→severidad, MITRE, agente, IPs. Filtros: `min_level`, `rule_group`, `limit` |
| `local_json` | JSON/NDJSON en `data/connectors` | Genérico (sandbox). Param: `path`, `limit` |
| `local_csv` | CSV en `data/connectors` | Filas como registros. Param: `path`, `delimiter`, `limit` |
| `http_json` | Endpoint JSON de la allow-list | **Opt-in**. Param: `url`, `list_key`, `limit` |

## Configurar el conector de Wazuh

Wazuh escribe sus alertas en `/var/ossec/logs/alerts/alerts.json`. Dos opciones:

1. **Apuntar a la ruta real** (la máquina es tuya): define en `.env`
   `WAZUH_ALERTS_PATH=/var/ossec/logs/alerts/alerts.json`.
2. **Copiar/symlink** a la carpeta del sandbox: `backend/data/connectors/wazuh/alerts.json`
   (es la ruta por defecto). El script de ejemplo copia ahí unas alertas de muestra.

## API

```http
GET  /connectors                  # catálogo (incluye 'enabled' según configuración)
GET  /connectors/categories       # por categoría
POST /connectors/{name}/read      # vista previa: lee la fuente (acción del operador)
```

Vista previa de Wazuh:

```json
POST /connectors/wazuh_alerts/read
{ "params": { "min_level": 7, "limit": 20 }, "max_records": 20 }
```

## Configuración

| Variable | Por defecto | Descripción |
|---|---|---|
| `ENABLE_HTTP_CONNECTORS` | `false` | Habilita los conectores de red (opt-in) |
| `HTTP_CONNECTOR_ALLOWLIST` | `""` | Hosts permitidos para `http_json` (coma-separados) |
| `WAZUH_ALERTS_PATH` | `""` | Ruta del `alerts.json` (vacío = sandbox) |
| `CONNECTOR_TIMEOUT` | `15` | Timeout de los conectores de red (s) |

## Cómo añadir un conector

1. Crea una clase en `backend/app/connectors/` heredando de `BaseConnector`: `name`,
   `category`, `input_schema` (Pydantic) y `read()` que devuelve `ConnectorResult`. Solo
   lectura; usa `resolve_sandboxed`/`resolve_source` para las rutas.
2. Regístralo en `build_default_connector_registry()`.
3. Autorízalo en los agentes que lo necesiten (`data_access`).
4. Añade un test.
