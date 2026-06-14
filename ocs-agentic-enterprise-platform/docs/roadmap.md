# Roadmap

Estado actual: **Fase 3** (44 agentes por áreas, 24 herramientas, equipos multi-agente,
programador de tareas, conectores de datos con acceso por agente, Chain-of-Work, RAG híbrido,
dashboard de métricas, exportación de informes, gestor `.bat`, 127 tests).

## Completado en la Fase 3

- [x] **44 agentes especializados** por áreas (programación, ciberseguridad —blue/red/purple
      team, SOC, OT—, psicología —incl. de la ciberseguridad—, negocio, RRHH, compliance…)
      y 5 herramientas de análisis estático de código deterministas.
- [x] **Equipos (squads) multi-agente** en cadena, predefinidos y ad-hoc, en una única
      ejecución auditable (ver [`squads.md`](squads.md)).
- [x] **Programador de tareas** local puntual/periódico (once/interval/daily/weekly/cron)
      con zona horaria (ver [`scheduler.md`](scheduler.md)).
- [x] **Conectores de datos** (Wazuh, JSON/CSV, HTTP opt-in) con **acceso de lectura por
      agente** (`data_access`) y lectura automática desde el programador, p. ej. el **bucle
      del SOC** (ver [`connectors.md`](connectors.md) y [`use_cases.md`](use_cases.md)).
- [x] **Pentesting con Kali** (opt-in, alcance autorizado, sin shell): los agentes de
      ciberseguridad lanzan nmap/nikto/nuclei/… sobre objetivos autorizados y redactan el
      informe (ver [`pentest.md`](pentest.md)). Borrado de ejecuciones en API y UI.

## Completado en la Fase 2

- [x] **RAG semántico**: embeddings de Ollama (`nomic-embed-text`) en SQLite
      (tabla `chunk_embeddings`) y búsqueda híbrida keyword + coseno, con degradación
      elegante a keyword si Ollama no está disponible.
- [x] **Exportación** de ejecuciones a Markdown y HTML (informe autocontenido).
- [x] **Dashboard de métricas**: KPIs, gráficos y línea de actividad.
- [x] **Frontend rediseñado** (navegación lateral, anillo de confianza, timeline CoW).
- [x] **Gestor todo-en-uno `OCS-Platform.bat`** para Windows.

## Corto plazo

- [ ] **Índice vectorial dedicado** (ChromaDB local opcional) para escalar el RAG semántico
      más allá del cálculo de coseno en Python.
- [ ] **Streaming de tokens** (SSE) para ver la respuesta del agente en tiempo real.
- [ ] **Exportación a PDF** (además de Markdown/HTML).
- [ ] **Cancelación** de ejecuciones en curso desde el frontend.
- [ ] Edición de la tarea desde la vista previa de enrutado (re-clasificación en vivo).

## Medio plazo

- [ ] **Multiusuario con roles** (la tabla `users` y `required_role` de herramientas ya
      existen): API keys por usuario, permisos por categoría de agente.
- [ ] **Colaboración multi-agente real**: pipelines configurables (salida de un agente como
      entrada de otro), más allá de las notas auxiliares actuales.
- [ ] **Programador de tareas** local (ejecuciones recurrentes: informes semanales, etc.).
- [ ] **Métricas**: panel de uso por agente/modelo, latencias, tasa de verificación fallida.
- [ ] Clasificador de intención entrenable con feedback del usuario (correcciones de enrutado).
- [ ] Soporte DOCX y OCR opcional para PDFs escaneados.

## Largo plazo

- [ ] Proveedores LLM locales adicionales (llama.cpp server, LM Studio) tras el mismo contrato.
- [ ] Memoria de largo plazo por agente (preferencias y contexto de la organización).
- [ ] Catálogo de agentes/herramientas instalables como plugins.
- [ ] Confianza calibrada con histórico de validaciones humanas.
- [ ] Modo "borrador → revisión humana → aprobado" con firmas en el Chain-of-Work.

## Criterios para incorporar funcionalidades

1. Debe poder funcionar **100% en local** sin servicios obligatorios de terceros.
2. Debe dejar rastro auditable en el Chain-of-Work.
3. No puede relajar las reglas de seguridad de herramientas.
4. Si una capacidad no está implementada, la plataforma debe declararlo (nunca aparentarla).
