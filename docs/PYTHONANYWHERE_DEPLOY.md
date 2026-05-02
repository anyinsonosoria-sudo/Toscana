# Despliegue En PythonAnywhere

Esta app ya tiene pistas concretas para PythonAnywhere dentro del repo:

- Repo esperado en el servidor: `~/Toscana`
- Archivo WSGI esperado: `/var/www/toscana_pythonanywhere_com_wsgi.py`
- Entry point de la app: `wsgi.py`
- Verificación post-despliegue: `scripts/verify_deployment.py`
- Reparación de esquema/BD: `scripts/fix_db_pythonanywhere.py`

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
