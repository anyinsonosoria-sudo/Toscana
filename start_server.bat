@echo off
echo ========================================
echo   Building Maintenance System v2.0
echo   Iniciando servidor...
echo ========================================
echo.

cd /d "%~dp0"

REM Verificar si existe entorno virtual en el proyecto
if exist ".venv\Scripts\python.exe" (
    echo [INFO] Usando entorno virtual local (.venv)
    .venv\Scripts\python.exe app.py
) else if exist "..\.venv\Scripts\python.exe" (
    echo [INFO] Usando entorno virtual del directorio padre
    ..\.venv\Scripts\python.exe app.py
) else (
    echo [INFO] Usando Python del sistema
    python app.py
)

pause
