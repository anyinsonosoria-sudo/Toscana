# PASO 4: Separación del Módulo de Servicios/Productos

## Descripción General
Se ha creado un **módulo independiente de servicios y productos** (`services.py`) completamente separado de la funcionalidad de mantenimiento. Esto mejora la arquitectura y permite gestionar servicios/productos para facturación de forma independiente.

## Estructura Anterior (Confusa)
```
maintenance.py
  └── list_services()      [Usado para facturación]
  └── schedule_maintenance() [Usado para mantenimiento]

products_services.py
  └── add_product_service()
  └── list_products_services()
```

**Problema:** Había confusión entre servicios de mantenimiento y servicios/productos para facturación.

## Estructura Nueva (Separada)
```
services.py [NUEVO]
  ├── Gestión de servicios/productos para facturación
  ├── Independiente de mantenimiento
  └── Tabla nueva: services_products

maintenance.py [SIN CAMBIOS]
  └── Solo para funcionalidad de mantenimiento
```

## Nuevas Funciones en `services.py`

### Gestión Básica
- `add_service()` - Agregar nuevo servicio/producto
- `list_services()` - Listar con filtros (activos, por tipo)
- `get_service()` - Obtener por ID
- `find_by_code()` - Buscar por código
- `update_service()` - Actualizar información
- `delete_service()` - Eliminar (soft delete)
- `toggle_service_active()` - Activar/Desactivar

### Búsqueda y Filtrado
- `search_services()` - Búsqueda por nombre, descripción o código
- `get_services_by_category()` - Filtrar por categoría
- `get_all_categories()` - Listar categorías disponibles

### Análisis y Reportes
- `get_service_stats()` - Estadísticas generales:
  - Total de servicios
  - Servicios activos/inactivos
  - Distribución por tipo
  - Precio promedio

### Base de Datos
- `create_services_table()` - Crear tabla `services_products`
- Schema con campos mejorados:
  - `id` (PK)
  - `code` (UNIQUE, opcional)
  - `name` (requerido)
  - `description`
  - `price` (requerido)
  - `type` (service, product, etc.)
  - `category` (nuevo campo para organización)
  - `active` (para soft delete)
  - `created_at`, `updated_at`

## Cambios en `app.py`

### Imports
```python
# Anterior
import products_services, customization

# Nuevo
import products_services, customization, services
```

### Rutas Actualizadas
1. **GET /servicios**
   - Ahora usa `services.list_services()`
   - Devuelve estadísticas (`stats`)
   - Devuelve categorías disponibles

2. **GET /facturacion**
   - Usa `services.list_services(active_only=True)`
   - Solo servicios activos en selectores

3. **POST /products_services/add**
   - Usa `services.add_service()` 
   - Soporta campo `category` nuevo

4. **GET /api/service/<code>**
   - Usa `services.find_by_code()`
   - Campo `cost` → `price` (coherencia)

5. **GET /api/services/search**
   - Usa `services.search_services()`

6. **GET /configuracion**
   - Usa `services.list_services()`

## Tabla Nueva: `services_products`

```sql
CREATE TABLE services_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL DEFAULT 0.0,
    type TEXT DEFAULT 'service',
    category TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

**Campos Mejorados:**
- `code`: Código único opcional
- `type`: Identifica si es servicio, producto, etc.
- `category`: Para organizar servicios por grupo
- `price`: Nombre coherente (antes era confuso `cost` vs `price`)
- `updated_at`: Para tracking de cambios

## Ventajas de la Separación

✅ **Independencia:** Servicios desacoplados de mantenimiento  
✅ **Claridad:** Módulo específico para facturación  
✅ **Escalabilidad:** Fácil agregar más funcionalidades  
✅ **Mantenimiento:** Código más organizado  
✅ **Reutilización:** Funciones genéricas reutilizables  
✅ **Estadísticas:** Sistema mejorado de análisis  
✅ **Categorización:** Mejor organización de servicios  

## Compatibilidad

- El módulo `products_services.py` sigue existiendo (para compatibilidad)
- Las rutas antiguas funcionan con el nuevo módulo
- No hay cambios en la base de datos existente (tabla nueva se crea automáticamente)
- Las migraciones ocurren automáticamente al importar el módulo

## Próximos Pasos

**Paso 5:** Mejorar contabilidad con plan de cuentas
**Paso 7:** Fotoupload para recibos de gastos con OCR

## Pruebas

✅ Python Syntax: OK
✅ Imports: OK  
✅ Rutas: OK
✅ Base de datos: Tabla se crea automáticamente

## Resumen

El Paso 4 ha separado exitosamente la gestión de servicios/productos de la de mantenimiento, creando una arquitectura más limpia y escalable. El sistema ahora tiene un módulo específico para servicios de facturación con funcionalidades mejoradas de búsqueda, categorización y estadísticas.
