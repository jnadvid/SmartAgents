#!/usr/bin/env bash
# Instala las herramientas de pentest que usa la plataforma en Kali/Debian.
# Idempotente: se puede re-ejecutar. Pensado para correr como root dentro de Kali
# (lo invoca install-kali-windows.ps1 en modo WSL, o ejecútalo en tu Kali nativo).
set -euo pipefail

PACKAGES=(
  # OSINT / DNS
  whois dnsutils dnsrecon subfinder amass theharvester
  # Puertos y servicios
  nmap
  # Recon web / TLS / CMS
  whatweb httpx-toolkit wafw00f sslscan testssl.sh cmseek
  # Enumeración por servicio
  enum4linux smbmap ssh-audit
  # Escaneo web / vulnerabilidades
  nikto nuclei gobuster feroxbuster ffuf
  # CMS específicos
  wpscan joomscan droopescan
  # Explotación / exploits
  sqlmap dalfox exploitdb
  # Diccionarios
  seclists
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
for bin in whois dig dnsrecon subfinder amass theHarvester nmap whatweb httpx wafw00f \
           sslscan testssl.sh cmseek enum4linux smbmap ssh-audit nikto nuclei gobuster \
           feroxbuster ffuf wpscan joomscan droopescan sqlmap dalfox searchsploit; do
  if command -v "$bin" >/dev/null 2>&1; then
    echo "    [ok] $bin"
  else
    echo "    [--] $bin (no instalado)"
  fi
done

echo
echo "[✓] Provisión completada. Configura en la plataforma: modo de ejecución 'wsl' (Windows) o 'native' (Kali)."
