#!/bin/bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/Toscana}"
VENV_PATH="${VENV_PATH:-}"
WSGI_FILE="${WSGI_FILE:-/var/www/toscana_pythonanywhere_com_wsgi.py}"
PYTHON_BIN="python3"

echo "== PythonAnywhere deploy helper =="
echo "App dir: $APP_DIR"
echo "WSGI file: $WSGI_FILE"

cd "$APP_DIR"

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Hay cambios locales sin commit en PythonAnywhere. Revísalos antes de continuar:"
    git status --short
    exit 1
fi

git pull --ff-only origin main

if [[ -n "$VENV_PATH" ]]; then
    if [[ ! -f "$VENV_PATH/bin/activate" ]]; then
        echo "No existe el virtualenv indicado: $VENV_PATH"
        exit 1
    fi
    # shellcheck disable=SC1090
    source "$VENV_PATH/bin/activate"
    PYTHON_BIN="python"
fi

"$PYTHON_BIN" -m pip install -r requirements.txt
"$PYTHON_BIN" scripts/fix_db_pythonanywhere.py
"$PYTHON_BIN" scripts/verify_deployment.py
touch "$WSGI_FILE"

echo
echo "Despliegue actualizado y aplicación recargada."