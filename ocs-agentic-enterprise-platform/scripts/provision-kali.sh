#!/usr/bin/env bash
# Instala las herramientas de pentest que usa la plataforma.
#
# Funciona en Kali (todo por apt) y, en lo posible, en Debian/Ubuntu (apt para lo
# disponible + instaladores alternativos: go, pipx, gem, git). Es best-effort e
# idempotente: ningún fallo individual aborta el resto. Al final muestra qué quedó
# instalado. Ejecuta como root dentro de tu distro (o con sudo).
#
#   sudo bash scripts/provision-kali.sh
set -uo pipefail

export DEBIAN_FRONTEND=noninteractive
SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

OPT=/opt
BIN=/usr/local/bin
IS_KALI=false
grep -qi kali /etc/os-release 2>/dev/null && IS_KALI=true

note() { echo "[*] $*"; }
ok()   { echo "    [ok] $*"; }
warn() { echo "    [!] $*"; }
have() { command -v "$1" >/dev/null 2>&1; }
apt1() { $SUDO apt-get install -y "$1" >/dev/null 2>&1 && ok "apt $1" || return 1; }

note "Sistema: $(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-desconocido}") · Kali=$IS_KALI"
note "Actualizando índices de apt…"
$SUDO apt-get update -y >/dev/null 2>&1 || warn "apt update falló (continuo)."

# --- utilidades base para los instaladores alternativos ---
note "Preparando gestores (git, pipx, go, ruby)…"
for base in git curl wget build-essential perl smbclient python3-pip pipx golang-go ruby ruby-dev; do
  apt1 "$base" >/dev/null 2>&1
done
have pipx || $SUDO python3 -m pip install --break-system-packages pipx >/dev/null 2>&1 || true
export PATH="$PATH:/root/go/bin:$HOME/go/bin:$BIN"

go_install() {  # go_install <import_path> <binname>
  have go || return 1
  note "go install $2…"
  GOBIN="$BIN" $SUDO env "PATH=$PATH" GOBIN="$BIN" go install "$1@latest" >/dev/null 2>&1 \
    && ok "go $2" || warn "no se pudo compilar $2 con go"
}
pipx_install() { $SUDO pipx install "$1" >/dev/null 2>&1 || $SUDO python3 -m pip install --break-system-packages "$1" >/dev/null 2>&1; }
git_wrapper() {  # git_wrapper <repo> <dir> <wrapper_name> <run_cmd...>
  local repo="$1" dir="$2" name="$3"; shift 3
  [ -d "$dir" ] || $SUDO git clone --depth 1 "$repo" "$dir" >/dev/null 2>&1
  printf '#!/usr/bin/env bash\nexec %s "$@"\n' "$*" | $SUDO tee "$BIN/$name" >/dev/null
  $SUDO chmod +x "$BIN/$name"
}

# ---------------------------------------------------------------------------
# 1) Paquetes de apt (disponibles en Kali; en Ubuntu solo algunos)
# ---------------------------------------------------------------------------
note "Instalando paquetes base por apt…"
for p in whois dnsutils dnsrecon nmap whatweb wafw00f sslscan nikto gobuster sqlmap \
         smbmap ssh-audit ffuf amass; do
  apt1 "$p" >/dev/null 2>&1
done
# En Kali, intenta también los específicos por apt (más rápido que compilar).
if $IS_KALI; then
  for p in subfinder nuclei httpx-toolkit theharvester enum4linux feroxbuster wpscan \
           joomscan droopescan dalfox cmseek exploitdb seclists testssl.sh metasploit-framework; do
    apt1 "$p" >/dev/null 2>&1
  done
fi

# ---------------------------------------------------------------------------
# 2) Instaladores alternativos para lo que falte (multi-distro)
# ---------------------------------------------------------------------------
note "Completando herramientas que falten…"

# ProjectDiscovery y otras en Go
have subfinder   || go_install github.com/projectdiscovery/subfinder/v2/cmd/subfinder subfinder
have nuclei      || go_install github.com/projectdiscovery/nuclei/v3/cmd/nuclei nuclei
have httpx       || go_install github.com/projectdiscovery/httpx/cmd/httpx httpx
have dnsx        || go_install github.com/projectdiscovery/dnsx/cmd/dnsx dnsx
have dalfox      || go_install github.com/hahwul/dalfox/v2 dalfox
have ffuf        || go_install github.com/ffuf/ffuf/v2 ffuf
have amass       || go_install github.com/owasp-amass/amass/v4/... amass

# feroxbuster (binario oficial)
if ! have feroxbuster; then
  note "Instalando feroxbuster…"
  curl -sL https://raw.githubusercontent.com/epi052/feroxbuster/main/install-nix.sh 2>/dev/null | $SUDO bash -s -- "$BIN" >/dev/null 2>&1 \
    && ok "feroxbuster" || warn "no se pudo instalar feroxbuster"
fi

# Python (pipx)
have theHarvester || { note "theHarvester…"; pipx_install theHarvester && ok "theHarvester"; }
have droopescan   || { note "droopescan…"; pipx_install droopescan && ok "droopescan"; }
have enum4linux   || pipx_install enum4linux-ng >/dev/null 2>&1 || true
have enum4linux || { curl -sL https://raw.githubusercontent.com/CiscoCXSecurity/enum4linux/master/enum4linux.pl 2>/dev/null | $SUDO tee "$BIN/enum4linux" >/dev/null && $SUDO chmod +x "$BIN/enum4linux" && ok "enum4linux"; }
have smbmap     || pipx_install smbmap >/dev/null 2>&1 || true
have ssh-audit  || pipx_install ssh-audit >/dev/null 2>&1 || true

# Ruby (wpscan)
have wpscan || { note "wpscan (gem)…"; $SUDO gem install wpscan >/dev/null 2>&1 && ok "wpscan" || warn "no se pudo instalar wpscan"; }

# Git + wrapper
have cmseek      || git_wrapper https://github.com/Tuhinshubhra/CMSeeK "$OPT/CMSeeK" cmseek "python3 $OPT/CMSeeK/cmseek.py"
have joomscan    || git_wrapper https://github.com/OWASP/joomscan "$OPT/joomscan" joomscan "perl $OPT/joomscan/joomscan.pl"
have testssl.sh  || git_wrapper https://github.com/drwetter/testssl.sh "$OPT/testssl.sh" testssl.sh "$OPT/testssl.sh/testssl.sh"
have searchsploit || { $SUDO git clone --depth 1 https://gitlab.com/exploit-database/exploitdb "$OPT/exploitdb" >/dev/null 2>&1; $SUDO ln -sf "$OPT/exploitdb/searchsploit" "$BIN/searchsploit"; }

# SecLists (diccionarios)
[ -d /usr/share/seclists ] || { note "SecLists…"; $SUDO git clone --depth 1 https://github.com/danielmiessler/SecLists /usr/share/seclists >/dev/null 2>&1 && ok "seclists"; }

# Metasploit Framework (instalador oficial si no está)
if ! have msfconsole; then
  note "Instalando Metasploit Framework (puede tardar)…"
  curl -sSL https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb -o /tmp/msfinstall 2>/dev/null \
    && $SUDO chmod +x /tmp/msfinstall && $SUDO /tmp/msfinstall >/dev/null 2>&1 \
    && ok "metasploit-framework" || warn "no se pudo instalar Metasploit automáticamente"
fi

# ---------------------------------------------------------------------------
# 3) Verificación
# ---------------------------------------------------------------------------
echo
note "Verificación de binarios:"
INSTALLED=0; TOTAL=0
for bin in whois dig dnsrecon subfinder amass theHarvester nmap whatweb httpx wafw00f \
           sslscan testssl.sh cmseek enum4linux smbmap ssh-audit nikto nuclei gobuster \
           feroxbuster ffuf wpscan joomscan droopescan sqlmap dalfox searchsploit \
           msfconsole msfvenom; do
  TOTAL=$((TOTAL+1))
  if have "$bin"; then echo "    [ok] $bin"; INSTALLED=$((INSTALLED+1)); else echo "    [--] $bin (no instalado)"; fi
done

echo
note "Instaladas $INSTALLED/$TOTAL herramientas."
if [ "$INSTALLED" -lt "$TOTAL" ]; then
  echo "    Para el toolkit COMPLETO sin complicaciones, usa Kali Linux (WSL): install-kali-windows.ps1."
  echo "    Asegúrate de tener 'go', 'pipx', 'gem' y 'git' si quieres los instaladores alternativos."
fi
echo "[✓] En la plataforma → Ajustes: entorno 'wsl' (Windows) o 'native' (Kali/Linux)."
