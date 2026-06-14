<#
.SYNOPSIS
    Instala Kali Linux en WSL (Windows) y aprovisiona las herramientas de pentest
    que usa la OCS Agentic Enterprise Platform.

.DESCRIPTION
    1. Comprueba/instala WSL (puede requerir reinicio la primera vez).
    2. Instala la distro kali-linux si no está.
    3. Ejecuta provision-kali.sh dentro de Kali (nmap, nikto, nuclei, etc.).

    Tras instalar, en la plataforma ve a Ajustes y selecciona el entorno de
    ejecucion "WSL" (y la distro "kali-linux").

.NOTES
    Ejecutar en PowerShell como Administrador la primera vez (para habilitar WSL).
    Uso:  powershell -ExecutionPolicy Bypass -File scripts\install-kali-windows.ps1
          [-Distro kali-linux] [-SkipProvision]
#>
[CmdletBinding()]
param(
    [string]$Distro = "kali-linux",
    [switch]$SkipProvision
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    [ok] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    [!] $msg" -ForegroundColor Yellow }

Write-Step "Comprobando WSL"
$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    Write-Warn "WSL no está instalado. Habilitándolo (puede requerir REINICIO)…"
    # Win10 2004+/Win11: habilita WSL + Virtual Machine Platform e instala el kernel.
    wsl.exe --install --no-distribution
    Write-Warn "Si te pide reiniciar, hazlo y vuelve a ejecutar este script."
} else {
    wsl.exe --update 2>$null | Out-Null
    Write-Ok "WSL disponible."
}

Write-Step "Comprobando la distro '$Distro'"
$installed = (& wsl.exe -l -q) 2>$null | ForEach-Object { $_.Trim() }
if ($installed -notcontains $Distro) {
    Write-Warn "'$Distro' no está instalada. Instalando…"
    wsl.exe --install -d $Distro
    Write-Warn "Si es la primera vez, completa el usuario/contraseña de Kali cuando se abra y vuelve a ejecutar con -SkipProvision:0."
} else {
    Write-Ok "'$Distro' ya está instalada."
}

if ($SkipProvision) {
    Write-Step "Provisión omitida (-SkipProvision)."
    return
}

Write-Step "Aprovisionando herramientas dentro de '$Distro'"
$provision = Join-Path $PSScriptRoot "provision-kali.sh"
if (-not (Test-Path $provision)) {
    Write-Warn "No se encontró provision-kali.sh junto a este script."
    return
}
try {
    $wslPath = (& wsl.exe -d $Distro wslpath -u "$provision").Trim()
    # Normaliza finales de línea y ejecuta como root dentro de Kali.
    wsl.exe -d $Distro -u root -- bash -lc "sed -i 's/\r$//' '$wslPath'; bash '$wslPath'"
    Write-Ok "Herramientas instaladas en '$Distro'."
} catch {
    Write-Warn "No se pudo aprovisionar automáticamente: $($_.Exception.Message)"
    Write-Warn "Abre Kali y ejecuta manualmente: sudo bash $provision"
}

Write-Step "Listo"
Write-Host "En la plataforma -> Ajustes -> Entorno de ejecución: 'WSL', Distro: '$Distro'." -ForegroundColor Green
Write-Host "Y define tu alcance autorizado (PENTEST_SCOPE_ALLOWLIST) antes de escanear." -ForegroundColor Green
