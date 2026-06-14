#!/usr/bin/env bash
# Instala las herramientas de pentest que usa la plataforma en Kali/Debian.
# Idempotente: se puede re-ejecutar. Pensado para correr como root dentro de Kali
# (lo invoca install-kali-windows.ps1 en modo WSL, o ejecútalo en tu Kali nativo).
set -euo pipefail

PACKAGES=(
  nmap          # puertos y servicios (+ NSE vuln)
  whatweb       # fingerprinting web
  wafw00f       # detección de WAF
  sslscan       # análisis TLS/SSL
  dnsrecon      # enumeración DNS
  nikto         # escáner web
  gobuster      # fuzzing de directorios
  feroxbuster   # descubrimiento de contenido recursivo
  sqlmap        # inyección SQL
  wpscan        # escáner de WordPress
  subfinder     # subdominios (pasivo)
  theharvester  # OSINT pasivo
  httpx-toolkit # sondeo web (projectdiscovery; binario 'httpx')
  seclists      # diccionarios (wordlists)
)

echo "[*] Actualizando índices de paquetes…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y

echo "[*] Instalando: ${PACKAGES[*]}"
apt-get install -y "${PACKAGES[@]}"

# nuclei puede no estar en todos los repos; se intenta aparte sin romper el resto.
echo "[*] Instalando nuclei (best-effort)…"
apt-get install -y nuclei || echo "[!] nuclei no se pudo instalar por apt; instálalo manualmente si lo necesitas."

echo
echo "[*] Verificación de binarios:"
for bin in nmap whatweb wafw00f sslscan dnsrecon nikto gobuster feroxbuster sqlmap wpscan subfinder theHarvester httpx nuclei; do
  if command -v "$bin" >/dev/null 2>&1; then
    echo "    [ok] $bin"
  else
    echo "    [--] $bin (no instalado)"
  fi
done

echo
echo "[✓] Provisión completada. Configura en la plataforma: modo de ejecución 'wsl' (Windows) o 'native' (Kali)."
