@echo off
setlocal

cd /d "%~dp0\.."

set "PYTHON_EXE=.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

if not exist "logs" (
    mkdir "logs"
)

echo [%date% %time%] Iniciando envio mensual solo a administrador...>>"logs\monthly_report_task.log"
if "%~1"=="" (
    "%PYTHON_EXE%" "scripts\send_monthly_report.py" --mode dispatch --admin-only >>"logs\monthly_report_task.log" 2>&1
) else (
    "%PYTHON_EXE%" "scripts\send_monthly_report.py" --mode dispatch --admin-only --admin-email "%~1" >>"logs\monthly_report_task.log" 2>&1
)
set "TASK_EXIT_CODE=%ERRORLEVEL%"
echo [%date% %time%] Finalizado con codigo %TASK_EXIT_CODE%.>>"logs\monthly_report_task.log"

exit /b %TASK_EXIT_CODE%