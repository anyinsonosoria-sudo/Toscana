# Despliegue En PythonAnywhere

Esta app ya tiene pistas concretas para PythonAnywhere dentro del repo:

- Repo esperado en el servidor: `~/Toscana`
- Archivo WSGI esperado: `/var/www/toscana_pythonanywhere_com_wsgi.py`
- Entry point de la app: `wsgi.py`
- Verificación post-despliegue: `scripts/verify_deployment.py`
- Reparación de esquema/BD: `scripts/fix_db_pythonanywhere.py`

## Exportar la BD de PythonAnywhere y restaurarla localmente

La app usa SQLite. Por defecto, la BD activa vive en `~/Toscana/data/data.db`, aunque si en PythonAnywhere existe `BUILDING_MAINTENANCE_DB`, los scripts nuevos respetan esa ruta.

## Módulo web de backup/restore

La pantalla `Configuración -> Base de Datos` ahora incluye un módulo admin para:

- crear y descargar un backup consistente de la SQLite activa,
- restaurar un snapshot subido desde la interfaz web,
- guardar automáticamente un respaldo previo antes de restaurar.

Comportamiento por defecto:

- `WEB_DB_BACKUP_ENABLED=1`: el backup web queda habilitado.
- `WEB_DB_RESTORE_ENABLED=0` en producción: la restauración web queda deshabilitada por seguridad.
- `WEB_DB_RESTORE_ENABLED=1` fuera de producción: útil para tu ambiente local.

Si alguna vez quisieras habilitar restauración web también en PythonAnywhere, tendrías que hacerlo explícitamente en el entorno/Wsgi file:

```python
os.environ['WEB_DB_RESTORE_ENABLED'] = '1'
```

No es recomendable dejar esa bandera activa en un entorno público salvo que tengas un motivo operativo claro.

### 1. Crear el backup en PythonAnywhere

En una consola Bash de PythonAnywhere:

```bash
cd ~/Toscana
python3 scripts/export_db_snapshot.py
ls -lh backups/db
```

Eso genera un archivo como este:

```text
~/Toscana/backups/db/toscana-db-backup-20260516-233116.sqlite3
```

### 2. Descargar el archivo `.sqlite3`

Opciones prácticas:

- Desde la pestaña **Files** de PythonAnywhere, navega a `~/Toscana/backups/db/` y descarga el archivo.
- O por SSH/SCP desde tu máquina:

```bash
scp TU_USUARIO@ssh.pythonanywhere.com:~/Toscana/backups/db/toscana-db-backup-20260516-233116.sqlite3 .
```

### 3. Restaurar ese backup en tu máquina local

Primero cierra la app local si la tienes abierta para evitar que SQLite bloquee el archivo.

En PowerShell local:

```powershell
Set-Location "c:\Users\Usuario\OneDrive\Desktop\Toscana"
.\.venv\Scripts\python.exe .\scripts\restore_db_snapshot.py "C:\ruta\al\toscana-db-backup-20260516-233116.sqlite3"
```

Ese comando:

- valida que el archivo sea una BD SQLite de Toscana,
- crea un respaldo automático de tu `data/data.db` actual en `backups/db/`,
- reemplaza la base local por la copia descargada.

Si quieres validar el archivo sin reemplazar nada todavía:

```powershell
.\.venv\Scripts\python.exe .\scripts\restore_db_snapshot.py "C:\ruta\al\backup.sqlite3" --dry-run
```

### 4. Alinear esquema local con el código actual

Si tu código local está más adelantado que lo desplegado en PythonAnywhere, ejecuta después:

```powershell
.\.venv\Scripts\python.exe .\scripts\fix_db_pythonanywhere.py
```

### 5. Levantar la app y probar reportes

```powershell
.\.venv\Scripts\python.exe .\app.py
```

Con eso ya deberías poder probar los reportes mensuales con datos reales de producción en local.

## Opción 1: flujo recomendado con Git

### 1. Desde tu máquina local

Ejecuta estos comandos dentro de `Xpack/building_maintenance`:

```powershell
Set-Location "c:\Users\anyinson.osoria\OneDrive - PC Precision Engineering\Desktop\Xpack\Xpack\building_maintenance"
git status --short
git add app.py blueprints/billing.py senders.py templates/facturacion.html templates/pagos.html templates/registrar_pago.html templates/edit_payment.html tests/test_payment_edit_delete_notifications.py docs/PYTHONANYWHERE_DEPLOY.md scripts/deploy_pythonanywhere.sh
git commit -m "Add payment edit flow and admin-only payment change notifications"
git push origin main
```

Si prefieres agregar todo lo modificado en el repo:

```powershell
git add .
git commit -m "Add payment edit flow and admin-only payment change notifications"
git push origin main
```

### 2. En la consola Bash de PythonAnywhere

```bash
cd ~/Toscana
git pull --ff-only origin main
python3 -m pip install -r requirements.txt
python3 scripts/fix_db_pythonanywhere.py
python3 scripts/verify_deployment.py
touch /var/www/toscana_pythonanywhere_com_wsgi.py
```

Ese `touch` fuerza el reload del sitio.

## Opción 2: usar el script del repo en PythonAnywhere

El repo incluye `scripts/deploy_pythonanywhere.sh`.

Uso mínimo:

```bash
cd ~/Toscana
bash scripts/deploy_pythonanywhere.sh
```

Si tu sitio usa un virtualenv específico:

```bash
cd ~/Toscana
VENV_PATH="$HOME/.virtualenvs/toscana-venv" bash scripts/deploy_pythonanywhere.sh
```

Si el WSGI file tiene otro nombre, sobrescribe la ruta:

```bash
cd ~/Toscana
WSGI_FILE="/var/www/toscana_pythonanywhere_com_wsgi.py" bash scripts/deploy_pythonanywhere.sh
```

## Variables de entorno que deben existir en el WSGI de PythonAnywhere

Además del path/import de la app, el archivo WSGI debe definir al menos:

```python
import os
import sys

project_home = '/home/toscana/Toscana'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['FLASK_ENV'] = 'production'
os.environ['SECRET_KEY'] = 'tu-secret-key-segura'

os.environ['SMTP_HOST'] = 'smtp.gmail.com'
os.environ['SMTP_PORT'] = '587'
os.environ['SMTP_USER'] = 'tu_email@gmail.com'
os.environ['SMTP_PASSWORD'] = 'tu_app_password'
os.environ['SMTP_FROM'] = 'tu_email@gmail.com'

from wsgi import application
```

Si falta SMTP, las notificaciones por correo no van a salir aunque el despliegue quede arriba.

## Variables opcionales para activar el chat IA del residente en PythonAnywhere

Si no configuras estas variables, la pantalla `Ayuda` sigue funcionando con el asistente contextual interno del portal.

Si quieres habilitar el modo IA externo en PythonAnywhere, agrega tambien en el WSGI file:

```python
os.environ['RESIDENT_AI_CHAT_ENABLED'] = '1'
os.environ['RESIDENT_AI_API_URL'] = 'https://api.openai.com/v1/chat/completions'
os.environ['RESIDENT_AI_API_KEY'] = 'tu_api_key'
os.environ['RESIDENT_AI_MODEL'] = 'gpt-4o-mini'
os.environ['RESIDENT_AI_TIMEOUT_SECONDS'] = '20'
```

Despues de guardar el WSGI file, vuelve a ejecutar:

```bash
touch /var/www/toscana_pythonanywhere_com_wsgi.py
```

## Verificación rápida después del reload

1. Abre `https://toscana.pythonanywhere.com/ventas/registrar-pago`
2. Confirma que aparezca `Ver Historial Completo`
3. Abre `https://toscana.pythonanywhere.com/ventas/pagos`
4. Confirma que veas el icono de editar y el botón `Registrar Nuevo Pago`
5. Edita un pago y valida que el correo llegue solo al administrador

## Si el servidor falla después del pull

Ejecuta en PythonAnywhere:

```bash
cd ~/Toscana
python3 scripts/fix_db_pythonanywhere.py
python3 scripts/verify_deployment.py
tail -n 100 /var/log/toscana.pythonanywhere.com.error.log
```

## Nota sobre este cambio

Los archivos principales que deben terminar desplegados para esta funcionalidad son:

- `app.py`
- `blueprints/billing.py`
- `senders.py`
- `templates/facturacion.html`
- `templates/pagos.html`
- `templates/registrar_pago.html`
- `templates/edit_payment.html`
- `tests/test_payment_edit_delete_notifications.py`
