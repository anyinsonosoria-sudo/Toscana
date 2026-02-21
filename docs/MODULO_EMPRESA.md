# Módulo de Información de la Empresa/Administrador

## Descripción

Este módulo permite gestionar la información de la empresa o administrador que gestiona los cobros y pagos del edificio. Los datos configurados aquí se utilizan en facturas, recibos y documentos oficiales.

## Acceso

- **Ruta web:** http://localhost:5000/empresa
- **Menú:** Empresa (en el sidebar izquierdo)
- **Icono:** 🏢 Building-gear

## Información que se puede configurar

### 1. Información Básica
- **Nombre de la Empresa/Administrador** (obligatorio)
- RUT/ID Legal
- ID Tributario (Tax ID)

### 2. Dirección
- Dirección completa
- Ciudad
- País

### 3. Contacto
- Teléfono
- Email
- Sitio Web

### 4. Información Bancaria
- Nombre del Banco
- Número de Cuenta
- Código de Ruta/Swift/BIC

### 5. Adicional
- Ruta del Logo (para aparecer en facturas)
- Notas adicionales

## Base de Datos

La tabla `company_info` almacena toda esta información:

```sql
CREATE TABLE company_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    legal_id TEXT,
    address TEXT,
    city TEXT,
    country TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    bank_name TEXT,
    bank_account TEXT,
    bank_routing TEXT,
    tax_id TEXT,
    logo_path TEXT,
    notes TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

## Archivos del Módulo

1. **company.py** - Módulo Python con funciones CRUD:
   - `get_company_info()` - Obtiene la información actual
   - `update_company_info()` - Actualiza o crea la información
   - `has_company_info()` - Verifica si existe información configurada

2. **templates/empresa.html** - Interfaz web con formulario completo

3. **app.py** - Rutas Flask:
   - `GET /empresa` - Muestra el formulario
   - `POST /empresa/update` - Guarda la información

## Características

- ✅ Solo se mantiene un registro (el más reciente)
- ✅ Vista previa de cómo aparecerá la información
- ✅ Campos opcionales (solo nombre es obligatorio)
- ✅ Diseño responsivo con Bootstrap
- ✅ Iconos descriptivos para cada sección
- ✅ Panel de ayuda lateral
- ✅ Badge de estado (Configurada/Sin configurar)

## Uso Futuro

Esta información se utilizará automáticamente en:
- 📄 Facturas emitidas (PDF/HTML)
- 🧾 Recibos de pago
- 📋 Documentos oficiales
- 📧 Notificaciones por email

## Ejemplo de Uso

```python
from company import get_company_info, update_company_info

# Actualizar información
update_company_info(
    name="Administradora XYZ Ltda.",
    legal_id="12.345.678-9",
    email="admin@xyz.cl",
    phone="+56 9 1234 5678",
    bank_name="Banco Estado",
    bank_account="123456789"
)

# Obtener información
info = get_company_info()
if info:
    print(f"Empresa: {info['name']}")
    print(f"Email: {info['email']}")
```

## Notas

- El módulo detecta automáticamente si ya existe información y actualiza en lugar de crear duplicados
- Todos los campos excepto "nombre" son opcionales
- El timestamp `updated_at` se actualiza automáticamente cada vez que se guarda
