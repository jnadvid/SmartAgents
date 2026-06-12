# Roadmap

Estado actual: **MVP funcional** (16 agentes, 19 herramientas, orquestación completa,
Chain-of-Work, RAG por keywords, frontend, 82 tests).

## Corto plazo

- [ ] **RAG vectorial**: índice con embeddings de Ollama (`nomic-embed-text`) y ChromaDB
      local opcional. El contrato `BaseLLMProvider.embed()` ya está implementado y la
      columna `document_chunks.embedding_model` reservada.
- [ ] **Streaming de tokens** (SSE) para ver la respuesta del agente en tiempo real.
- [ ] **Exportación** de ejecuciones e informes a Markdown/PDF descargable.
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
