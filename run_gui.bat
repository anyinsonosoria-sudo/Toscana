@echo off
pushd "%~dp0"
REM Try pythonw (no console). If not found, fall back to python (console).
where pythonw >nul 2>&1
if %ERRORLEVEL%==0 (
    start "" pythonw "%~dp0main.py"
) else (
    where python >nul 2>&1
    if %ERRORLEVEL%==0 (
        start "" python "%~dp0main.py"
    ) else (
        echo No se encontró python ni pythonw en PATH. Abra main.py con su intérprete Python.
        pause
    )
)
popd
