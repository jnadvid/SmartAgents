# Descubrimiento de subdominios (OSINT)

La pestaña **Subdominios** construye la lista más completa posible de subdominios
de un dominio combinando varias fuentes y deduplicando, con atribución de origen
por cada subdominio. Es **OSINT pasivo**: no envía tráfico de ataque al objetivo,
por lo que no requiere el alcance autorizado del pentest (sí valida el formato del
dominio para evitar inyección).

## Fuentes

1. **Certificate Transparency (crt.sh)** — siempre disponible, solo necesita salida
   HTTP. No requiere herramientas ni WSL.
2. **Herramientas de Kali** (si el pentest está activo y están instaladas), todas en
   modo **pasivo**: `subfinder`, `assetfinder`, `findomain` y, opcionalmente,
   `amass` (más lento). Se ejecutan por el runner robusto (WSL/nativo).
3. **Documentos subidos** — informes, listados o salidas de otras herramientas
   (TXT, CSV, JSON, logs, PDF…). Se extraen los subdominios del dominio indicado.

Los resultados de búsqueda y de documentos se **acumulan** en una única lista. Cada
subdominio muestra de qué fuentes proviene.

## Uso

1. Escribe el **dominio** (p. ej. `mi-dominio.com`).
2. **Buscar subdominios**: consulta crt.sh + las herramientas activas.
3. **Extraer de documentos**: sube ficheros; se reconocen los subdominios de ese
   dominio y se añaden a la lista.
4. **Resolver DNS** (opcional): marca cuáles están vivos y su IP.
5. **Exportar** la lista a TXT o CSV; **Filtrar** por texto; **Limpiar** para reiniciar.

## API

- `GET  /subdomains/status` — modo de ejecución y herramientas disponibles.
- `POST /subdomains/enumerate` — `{domain, use_tools, use_amass, resolve}`.
- `POST /subdomains/extract` — multipart: `domain` + `files[]`.
- `POST /subdomains/resolve` — `{domain, names[]}` → resuelve por DNS.

Todo es local: la resolución DNS usa el resolver del host y crt.sh es la única
llamada saliente (puede desactivarse cortando la red; el resto sigue funcionando).
