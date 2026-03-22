@echo off
setlocal
chcp 65001 >nul
REM Script local do Gustavo para rodar 3 instancias do Django
REM Porta 8000 - Admin
REM Porta 8001 - Solicitante
REM Porta 8002 - Projetista

REM Garante execucao a partir da pasta do script
pushd "%~dp0"

REM Valida venv e manage.py
set "PYTHON_EXE="
if exist "%~dp0.venv_local\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv_local\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%~dp0.venv2\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv2\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_EXE (
  echo ERRO: Nao encontrei um Python de venv neste projeto.
  echo Tentativas: .venv_local, .venv2, .venv
  echo.
  echo Crie uma venv e instale dependencias:
  echo   py -3 -m venv .venv
  echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)
if not exist "manage.py" (
  echo ERRO: Nao encontrei "manage.py" nesta pasta.
  echo.
  pause
  exit /b 1
)

echo Encerrando servidores antigos nas portas 8000, 8001 e 8002...
call :kill_port 8000
call :kill_port 8001
call :kill_port 8002
echo.

echo Iniciando 3 servidores Django (local)...
echo.

REM Abre Terminal 1 - Porta 8000 (Admin)
start "Django 8000 - Admin" cmd /k "cd /d "%~dp0" && echo PYTHON_EXE=%PYTHON_EXE% && "%PYTHON_EXE%" -c "import sys, django; print(sys.executable); print(django.get_version())" && set DJANGO_PORT=8000 && "%PYTHON_EXE%" manage.py runserver 0.0.0.0:8000"

REM Abre Terminal 2 - Porta 8001 (Solicitante)
start "Django 8001 - Solicitante" cmd /k "cd /d "%~dp0" && echo PYTHON_EXE=%PYTHON_EXE% && "%PYTHON_EXE%" -c "import sys, django; print(sys.executable); print(django.get_version())" && set DJANGO_PORT=8001 && "%PYTHON_EXE%" manage.py runserver 0.0.0.0:8001"

REM Abre Terminal 3 - Porta 8002 (Projetista)
start "Django 8002 - Projetista" cmd /k "cd /d "%~dp0" && echo PYTHON_EXE=%PYTHON_EXE% && "%PYTHON_EXE%" -c "import sys, django; print(sys.executable); print(django.get_version())" && set DJANGO_PORT=8002 && "%PYTHON_EXE%" manage.py runserver 0.0.0.0:8002"

echo.
echo Servidores iniciados!
echo.
echo Abra os navegadores:
echo - Admin:       http://127.0.0.1:8000/accounts/login
echo - Solicitante: http://127.0.0.2:8001/accounts/login
echo - Projetista:  http://127.0.0.3:8002/accounts/login
echo.
echo Dica: use sempre esses hosts diferentes para isolar cookies no navegador.
echo.
pause

popd
exit /b 0

:kill_port
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%1 .*LISTENING"') do (
  echo Finalizando PID %%P na porta %1...
  taskkill /PID %%P /F >nul 2>&1
)
exit /b 0
