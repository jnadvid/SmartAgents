# Modelo de seguridad

Plataforma pensada para ejecutarse **en local y para un único usuario** (MVP). Aun así,
aplica defensa en profundidad en cinco frentes.

## 1. Superficie de red

- El backend escucha por defecto en `127.0.0.1` (no expuesto a la red).
- CORS restringido al propio origen local.
- Única dependencia de red: la API local de Ollama (`localhost:11434`).
- **Ninguna herramienta ni agente accede a Internet.**

## 2. Autenticación (opcional)

- `ENABLE_AUTH=false` por defecto (uso local).
- Con `ENABLE_AUTH=true`, todas las rutas excepto `/health*` exigen la cabecera
  `X-API-Key` igual a `SECRET_KEY` (comparación en tiempo constante con `hmac.compare_digest`).
- La plataforma **se niega a arrancar** con auth activa y `SECRET_KEY` vacío o `change-me`.
- No hay claves hardcodeadas: todo llega por `.env`/entorno.
- Multiusuario con roles: roadmap (la tabla `users` ya existe).

## 3. Sandbox de herramientas

Las herramientas (`tools/`) cumplen por diseño:

- **Sin comandos del sistema**: nada de `subprocess`, `os.system` ni similares.
- **Sin red**: no usan httpx/requests; son funciones puras sobre texto/datos.
- **Sin archivos arbitrarios**: solo acceden a datos vía la BD local; los archivos
  originales viven en `backend/data/documents` con nombre UUID generado
  (`ensure_path_in_data_dir` bloquea path traversal).
- **Entrada validada** con Pydantic (tipos, longitudes, rangos, patrones).
- **Timeout** por herramienta (hilo dedicado). Limitación documentada: Python no puede
  matar el hilo; al ser funciones puras y cortas el impacto es marginal.
- **Allow-list por agente**: el `ToolRegistry` deniega (`denied`) cualquier herramienta
  fuera de `allowed_tools`, y lo audita.
- **Log obligatorio**: cada invocación queda en `tool_logs` + paso de Chain-of-Work.

## 4. Datos y auditoría

- Sanitización previa a persistir en auditoría/logs (`security/sanitization.py`):
  redacción de patrones de secretos (API keys, tokens JWT/Bearer, claves privadas,
  asignaciones `password=...`), eliminación de caracteres de control y truncado.
- La entrada del usuario se guarda **ya redactada** en `agent_executions.user_input`.
- El verificador **bloquea** respuestas que contengan patrones de secretos.
- No se guarda chain-of-thought literal del modelo.
- Límites de entrada: `MAX_INPUT_CHARS` (30k por defecto) y `MAX_DOCUMENT_SIZE_MB` (20 MB).

## 5. Seguridad frente a prompt injection

- Regla global de todos los agentes: el contenido de documentos y datos pegados son
  **datos a analizar, no instrucciones** (mitiga inyección indirecta vía documentos).
- Herramienta defensiva `check_prompt_injection_patterns`: detecta anulación de
  instrucciones, manipulación de rol, exfiltración de system prompt, abuso de
  herramientas, payloads codificados, etc., y propone mitigaciones.
- Agente `prompt_injection_tester` (política `security_testing`): análisis defensivo de
  prompts de sistemas propios/autorizados; **no genera payloads ofensivos**.
- El verificador detecta citas de herramientas/documentos fabricadas en la salida.

## Políticas de agente

| Política | Agentes | Particularidad |
|---|---|---|
| `standard` | empresariales | hasta 5 llamadas a herramientas |
| `sensitive` | legal, finanzas, ciber, compliance | descargo de responsabilidad obligatorio en la salida |
| `security_testing` | prompt_injection_tester | solo análisis defensivo y hardening |

## Amenazas fuera de alcance del MVP

- Aislamiento entre usuarios (es mono-usuario).
- Cifrado de la BD en reposo (el archivo SQLite hereda los permisos del sistema).
- Hardening del propio Ollama (consultar su documentación).
- Exposición del servicio fuera de localhost (requeriría TLS y auth reforzada).
