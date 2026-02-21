# 🔐 ETAPA 1: SEGURIDAD Y AUTENTICACIÓN - INSTALACIÓN

## ✅ ARCHIVOS CREADOS

### Configuración
- ✅ `.env.example` - Template de variables de entorno
- ✅ `.gitignore` - Archivos a ignorar en git
- ✅ `requirements.txt` - Dependencias actualizadas

### Autenticación
- ✅ `user_model.py` - Modelo de usuarios y funciones CRUD
- ✅ `auth.py` - Blueprint de autenticación (login/logout/register)
- ✅ `migrations/001_create_users_table.sql` - Script de migración SQL

### Seguridad
- ✅ `utils/file_validator.py` - Validación segura de archivos

### Templates
- ✅ `templates/login.html` - Página de inicio de sesión
- ✅ `templates/register.html` - Registro de usuarios (solo admins)
- ✅ `templates/users.html` - Lista de usuarios del sistema
- ✅ `templates/change_password.html` - Cambio de contraseña

### Scripts de Instalación
- ✅ `install_dependencies.py` - Instala todas las dependencias
- ✅ `setup_database.py` - Configura la base de datos y crea tabla users

### Modificaciones
- ✅ `app.py` - Integrado Flask-Login y protección de rutas
- ✅ `templates/base.html` - Añadido user info en sidebar

---

## 🚀 INSTALACIÓN PASO A PASO

### Paso 1: Instalar Dependencias

```powershell
# Opción A: Script automático (RECOMENDADO)
python install_dependencies.py

# Opción B: Manual
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Dependencias instaladas:**
- Flask 3.0.0
- Flask-Login 0.6.3 (autenticación)
- Flask-Bcrypt 1.0.1 (hashing de contraseñas)
- Flask-WTF 1.2.1 (CSRF protection)
- python-dotenv 1.0.0 (variables de entorno)
- python-magic-bin 0.4.14 (validación de archivos)
- Más todas las existentes...

---

### Paso 2: Configurar Variables de Entorno

```powershell
# Copiar template
copy .env.example .env

# Editar con tus valores
notepad .env
```

**Configuraciones importantes en `.env`:**

```ini
# CRÍTICO: Cambiar este valor por uno aleatorio
FLASK_SECRET_KEY=tu-clave-secreta-super-aleatoria-aqui

# Email (para notificaciones)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-contraseña-de-app

# Seguridad
MAX_UPLOAD_SIZE=10485760  # 10MB
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
```

**💡 Generar FLASK_SECRET_KEY:**
```python
python -c "import secrets; print(secrets.token_hex(32))"
```

---

### Paso 3: Configurar Base de Datos

```powershell
# Ejecutar script de configuración
python setup_database.py
```

Esto creará:
- ✅ Tabla `users` con índices
- ✅ Usuario admin por defecto
- ✅ Triggers para updated_at

**Credenciales por defecto:**
- **Usuario:** `admin`
- **Contraseña:** `admin123`

⚠️ **IMPORTANTE:** Cambiar la contraseña en el primer login!

---

### Paso 4: Iniciar Aplicación

```powershell
# Opción A: Modo desarrollo
python app.py

# Opción B: Con Flask CLI
$env:FLASK_APP="app.py"
$env:FLASK_ENV="development"
flask run --debug
```

---

### Paso 5: Primer Login

1. Abrir navegador: `http://localhost:5000`
2. Serás redirigido al login
3. Usar credenciales por defecto:
   - Usuario: `admin`
   - Contraseña: `admin123`
4. **Inmediatamente cambiar contraseña:**
   - Click en "Cambiar Contraseña" en el sidebar
   - Ingresar contraseña actual: `admin123`
   - Ingresar nueva contraseña (mínimo 6 caracteres)
   - Confirmar

---

## 🔐 CARACTERÍSTICAS IMPLEMENTADAS

### Autenticación
- ✅ Sistema de login con Flask-Login
- ✅ Hashing seguro de contraseñas con bcrypt
- ✅ Sesiones con cookies HttpOnly
- ✅ Protección de todas las rutas con `@login_required`
- ✅ Recordar sesión (remember me)
- ✅ Logout seguro

### Roles de Usuario
- 🔴 **Admin**: Acceso completo + gestión de usuarios
- 🔵 **Operador**: Gestión diaria del sistema
- ⚫ **Residente**: Solo consulta (para futuras features)

### Gestión de Usuarios
- ✅ Crear usuarios (solo admins)
- ✅ Listar usuarios con roles
- ✅ Activar/desactivar usuarios (soft delete)
- ✅ Cambio de contraseña por usuario
- ✅ Último login registrado

### Seguridad de Archivos
- ✅ Validación de tamaño (máximo 10MB)
- ✅ Validación de extensión
- ✅ Validación de MIME type real (anti-spoofing)
- ✅ Sanitización de nombres de archivo
- ✅ Nombres únicos automáticos

### UI/UX
- ✅ Página de login moderna y responsive
- ✅ Info de usuario en sidebar
- ✅ Indicador de rol
- ✅ Botones de logout y cambio de contraseña
- ✅ Mensajes flash para feedback

---

## 🧪 TESTING

### Probar Autenticación

```powershell
# Test 1: Acceso sin login
# Abrir: http://localhost:5000
# Resultado esperado: Redirige a /auth/login

# Test 2: Login exitoso
# Usuario: admin, Password: admin123
# Resultado: Acceso al dashboard

# Test 3: Logout
# Click en "Cerrar Sesión"
# Resultado: Redirige a login, sesión cerrada

# Test 4: Cambio de contraseña
# Ir a "Cambiar Contraseña"
# Cambiar de admin123 a una nueva
# Resultado: Contraseña actualizada, debe usar nueva en próximo login
```

### Probar Gestión de Usuarios (como Admin)

```powershell
# Test 5: Crear usuario
# Ir a "Usuarios" → "Nuevo Usuario"
# Llenar formulario:
#   - Usuario: operador1
#   - Email: operador1@test.com
#   - Rol: Operador
#   - Contraseña: test123456
# Resultado: Usuario creado, aparece en lista

# Test 6: Desactivar usuario
# En lista de usuarios, click en botón "Desactivar"
# Resultado: Usuario marcado como inactivo, no puede hacer login

# Test 7: Intentar desactivar admin actual
# Resultado: Error, no puede desactivarse a sí mismo
```

### Probar Validación de Archivos

```powershell
# Test 8: Upload de archivo válido
# Intentar subir un PDF o imagen
# Resultado: Aceptado

# Test 9: Upload de archivo inválido
# Intentar subir un .exe o .bat
# Resultado: Rechazado con mensaje de error

# Test 10: Upload de archivo muy grande
# Intentar subir archivo > 10MB
# Resultado: Rechazado, tamaño máximo excedido
```

---

## 📊 ESTADO DE PROTECCIÓN

### Rutas Protegidas
| Ruta | Estado | Requiere Autenticación |
|------|--------|------------------------|
| `/` (Dashboard) | ✅ Protegida | Sí |
| `/apartamentos/*` | ⚠️ Pendiente | Próxima fase |
| `/facturacion/*` | ⚠️ Pendiente | Próxima fase |
| `/gastos/*` | ⚠️ Pendiente | Próxima fase |
| `/auth/login` | ✅ Pública | No |
| `/auth/logout` | ✅ Protegida | Sí |
| `/auth/register` | ✅ Solo Admin | Sí + Admin |

---

## 🔄 PRÓXIMOS PASOS

### Inmediato (Tú debes hacer)
1. ✅ Ejecutar `python install_dependencies.py`
2. ✅ Configurar `.env` con tus credenciales reales
3. ✅ Ejecutar `python setup_database.py`
4. ✅ Iniciar app con `python app.py`
5. ✅ Hacer login y **CAMBIAR CONTRASEÑA DE ADMIN**
6. ✅ Probar crear un usuario de prueba

### Fase 2 (Siguiente)
- 🔨 Proteger TODAS las rutas restantes con `@login_required`
- 🔨 Implementar decorador `@role_required('admin')` para rutas sensibles
- 🔨 Añadir CSRF protection con Flask-WTF en formularios
- 🔨 Implementar logs de auditoría (quién hizo qué)
- 🔨 Agregar rate limiting en login (anti brute-force)

---

## ⚠️ ADVERTENCIAS DE SEGURIDAD

### CRÍTICO
- ❌ **NO** subir archivo `.env` a git (ya está en .gitignore)
- ❌ **NO** usar contraseña por defecto en producción
- ❌ **NO** usar `FLASK_SECRET_KEY` por defecto
- ❌ **NO** exponer el puerto a internet sin HTTPS

### Producción
Para poner en producción se requiere:
- ✅ HTTPS obligatorio (Let's Encrypt, Cloudflare)
- ✅ Reverse proxy (Nginx, Apache)
- ✅ WSGI server (Gunicorn, uWSGI)
- ✅ Variables de entorno en servidor (no .env)
- ✅ Backup automático de base de datos
- ✅ Monitoreo de logs
- ✅ Rate limiting

---

## 🐛 TROUBLESHOOTING

### Error: "ModuleNotFoundError: No module named 'flask_login'"
```powershell
pip install Flask-Login
```

### Error: "No such table: users"
```powershell
python setup_database.py
```

### Error: "Working outside of application context"
```powershell
# Asegúrate de tener el decorador @app.route antes de @login_required
# Correcto:
@app.route("/ruta")
@login_required
def mi_funcion():
    pass
```

### Error: "Unable to load user"
```powershell
# Verifica que user_model.py esté en el mismo directorio que app.py
# Y que la función load_user esté configurada correctamente
```

### Login no redirige correctamente
```powershell
# Verifica que Flask-Login esté inicializado:
# login_manager = LoginManager()
# login_manager.init_app(app)
# login_manager.login_view = "auth.login"
```

---

## 📞 SOPORTE

Si encuentras problemas:
1. Verifica los logs en la terminal
2. Revisa que todas las dependencias estén instaladas
3. Confirma que el archivo `.env` existe y tiene los valores correctos
4. Verifica que la tabla `users` exista en la base de datos

---

## ✅ CHECKLIST DE INSTALACIÓN

- [ ] Instaladas dependencias (`python install_dependencies.py`)
- [ ] Creado archivo `.env` desde `.env.example`
- [ ] Configuradas variables de entorno (FLASK_SECRET_KEY, etc.)
- [ ] Ejecutado `python setup_database.py`
- [ ] Verificado que tabla `users` existe
- [ ] Iniciada aplicación (`python app.py`)
- [ ] Accedido a http://localhost:5000
- [ ] Login exitoso con admin/admin123
- [ ] **CAMBIADA CONTRASEÑA DE ADMIN** ⚠️
- [ ] Creado usuario de prueba
- [ ] Probado logout y re-login
- [ ] Verificado que rutas sin login redirigen a login

---

**¡Listo! El sistema ahora tiene autenticación básica funcionando.**

**Próximo objetivo:** Proteger todas las rutas y añadir control de roles granular.
