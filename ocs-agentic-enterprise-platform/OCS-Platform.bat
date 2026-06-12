@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title OCS Agentic Enterprise Platform - Gestor
cd /d "%~dp0"

rem ============================================================
rem  OCS Agentic Enterprise Platform - Script todo-en-uno (Windows)
rem  Instala, configura y gestiona la plataforma local.
rem ============================================================

set "VENV=.venv"
set "VPY=%VENV%\Scripts\python.exe"
set "BACKEND_TITLE=OCS Backend"
set "URL=http://localhost:8000"

rem --- Detectar lanzador de Python (py -3 preferente, luego python) ---
set "PYLAUNCH="
py -3 --version >nul 2>&1 && set "PYLAUNCH=py -3"
if not defined PYLAUNCH (
  python --version >nul 2>&1 && set "PYLAUNCH=python"
)

rem --- Leer el modelo por defecto desde .env (si existe) ---
set "MODEL=llama3.1:8b"
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    if /i "%%a"=="DEFAULT_OLLAMA_MODEL" set "MODEL=%%b"
  )
)

:menu
cls
echo ============================================================
echo    OCS AGENTIC ENTERPRISE PLATFORM  ^|  Gestor local
echo ============================================================
echo    Carpeta : %CD%
echo    Python  : %PYLAUNCH%   Modelo Ollama : %MODEL%
echo ------------------------------------------------------------
echo.
echo    [1]  Instalacion completa (venv + dependencias + .env + BD)
echo    [2]  Preparar Ollama (arrancar servidor + descargar modelo)
echo    [3]  INICIAR plataforma (backend + navegador)
echo    [4]  Detener plataforma
echo    [5]  Estado del sistema
echo    [6]  Ejecutar tests
echo    [7]  Reindexar embeddings (RAG semantico)
echo    [8]  Abrir navegador
echo    [9]  Inicio rapido (instalar + Ollama + iniciar)
echo    [0]  Salir
echo.
set /p "OPT=  Elige una opcion: "

if "%OPT%"=="1" goto install
if "%OPT%"=="2" goto ollama
if "%OPT%"=="3" goto start
if "%OPT%"=="4" goto stop
if "%OPT%"=="5" goto status
if "%OPT%"=="6" goto tests
if "%OPT%"=="7" goto reindex
if "%OPT%"=="8" goto openbrowser
if "%OPT%"=="9" goto quickstart
if "%OPT%"=="0" goto end
goto menu

rem ============================================================
:install
cls
echo === Instalacion completa ===
echo.
if not defined PYLAUNCH (
  echo [ERROR] No se encontro Python. Instala Python 3.11+ desde https://python.org
  echo         y marca "Add Python to PATH".
  goto pause_menu
)

if not exist "%VPY%" (
  echo - Creando entorno virtual en %VENV% ...
  %PYLAUNCH% -m venv "%VENV%"
  if errorlevel 1 ( echo [ERROR] No se pudo crear el entorno virtual. & goto pause_menu )
) else (
  echo - Entorno virtual ya existe.
)

echo - Actualizando pip ...
"%VPY%" -m pip install --upgrade pip >nul

echo - Instalando dependencias (puede tardar) ...
"%VPY%" -m pip install -r backend\requirements.txt
if errorlevel 1 ( echo [ERROR] Fallo instalando dependencias. & goto pause_menu )

if not exist ".env" (
  echo - Creando .env a partir de .env.example ...
  copy /y ".env.example" ".env" >nul
) else (
  echo - .env ya existe (no se sobrescribe).
)

echo - Inicializando base de datos SQLite ...
"%VPY%" backend\app\database.py
if errorlevel 1 ( echo [ERROR] Fallo inicializando la base de datos. & goto pause_menu )

echo.
echo [OK] Instalacion completada.
goto pause_menu

rem ============================================================
:ollama
cls
echo === Preparar Ollama ===
echo.
where ollama >nul 2>&1
if errorlevel 1 (
  echo [AVISO] No se encontro 'ollama' en el PATH.
  echo         Instalalo desde https://ollama.com/download y vuelve a intentarlo.
  goto pause_menu
)

echo - Comprobando si el servidor de Ollama responde ...
curl -s -o nul http://localhost:11434/api/tags
if errorlevel 1 (
  echo - Arrancando 'ollama serve' en una ventana nueva ...
  start "Ollama" ollama serve
  echo   Esperando a que Ollama arranque ...
  timeout /t 4 /nobreak >nul
) else (
  echo - Ollama ya esta en ejecucion.
)

echo - Descargando modelo %MODEL% (puede tardar la primera vez) ...
ollama pull %MODEL%
echo - (Opcional) Descargando modelo de embeddings nomic-embed-text ...
ollama pull nomic-embed-text
echo.
echo [OK] Ollama preparado.
goto pause_menu

rem ============================================================
:start
cls
echo === Iniciar plataforma ===
echo.
if not exist "%VPY%" (
  echo [ERROR] No hay entorno virtual. Ejecuta primero la opcion [1] Instalacion.
  goto pause_menu
)
echo - Lanzando backend en una ventana nueva ("%BACKEND_TITLE%") ...
start "%BACKEND_TITLE%" "%VPY%" run_backend.py
echo - Esperando a que el servidor levante ...
timeout /t 5 /nobreak >nul
echo - Abriendo navegador en %URL% ...
start "" "%URL%"
echo.
echo [OK] Plataforma iniciada. Cierra la ventana "%BACKEND_TITLE%" o usa [4] para detener.
goto pause_menu

rem ============================================================
:stop
cls
echo === Detener plataforma ===
echo.
taskkill /FI "WINDOWTITLE eq %BACKEND_TITLE%*" /T /F >nul 2>&1
if errorlevel 1 (
  echo [AVISO] No se encontro la ventana del backend. ^(Quiza ya estaba detenido.^)
) else (
  echo [OK] Backend detenido.
)
goto pause_menu

rem ============================================================
:status
cls
echo === Estado del sistema ===
echo.
if defined PYLAUNCH (echo - Python ............. OK ^(%PYLAUNCH%^)) else (echo - Python ............. NO encontrado)
if exist "%VPY%" (echo - Entorno virtual .... OK) else (echo - Entorno virtual .... NO ^(usa opcion 1^))
if exist ".env" (echo - Configuracion .env . OK) else (echo - Configuracion .env . NO ^(usa opcion 1^))
if exist "backend\data\app.db" (echo - Base de datos ...... OK) else (echo - Base de datos ...... NO ^(usa opcion 1^))

echo - Ollama .............  (consultando...)
curl -s -o nul -w "    HTTP %%{http_code} en http://localhost:11434\n" http://localhost:11434/api/tags 2>nul || echo     no responde
echo - Backend ............  (consultando...)
curl -s -o nul -w "    HTTP %%{http_code} en %URL%\n" %URL%/health 2>nul || echo     no responde
goto pause_menu

rem ============================================================
:tests
cls
echo === Ejecutar tests ===
echo.
if not exist "%VPY%" ( echo [ERROR] Instala primero ^(opcion 1^). & goto pause_menu )
pushd backend
"..\%VPY%" -m pytest
popd
goto pause_menu

rem ============================================================
:reindex
cls
echo === Reindexar embeddings (RAG semantico) ===
echo.
echo - Requiere backend y Ollama en ejecucion.
curl -s -X POST %URL%/documents/reindex-embeddings
echo.
goto pause_menu

rem ============================================================
:openbrowser
start "" "%URL%"
goto menu

rem ============================================================
:quickstart
call :install
call :ollama
call :start
goto pause_menu

rem ============================================================
:pause_menu
echo.
pause
goto menu

:end
echo Hasta luego.
endlocal
