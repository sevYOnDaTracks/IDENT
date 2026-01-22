@echo off
setlocal

set "BASE=%~dp0"
set "VENV_PY=%BASE%.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [ERREUR] Environnement virtuel introuvable. Lancez "python -m venv .venv" puis "pip install -r requirements.txt".
  exit /b 1
)

set "IC1=C:\Program Files\Oracle\instantclient_23_8"
set "IC2=\\Sbureautique\sied\ndpartage\Dépendance\instantclient_23_8"

if exist "%IC1%" set "PATH=%IC1%;%PATH%"
if exist "%IC2%" set "PATH=%IC2%;%PATH%"

"%VENV_PY%" "%BASE%app.py"

endlocal
