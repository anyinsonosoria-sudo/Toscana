# Fase 2.3: Rate Limiting ✅

**Estado:** Completado  
**Fecha:** Enero 2026

## Resumen

Se ha implementado exitosamente rate limiting usando Flask-Limiter para proteger la aplicación contra ataques de fuerza bruta, abuso de recursos y peticiones excesivas.

## Componentes Implementados

### 1. Flask-Limiter Instalado

**Paquete:** `Flask-Limiter>=3.5.0`

```bash
pip install Flask-Limiter
```

Agregado a [requirements.txt](requirements.txt).

### 2. Configuración en Extensions

**Ubicación:** `extensions.py`

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)
```

**Parámetros:**
- **key_func:** `get_remote_address` - Identifica clientes por IP
- **default_limits:** Límites globales aplicados a todas las rutas
  - 200 requests por día
  - 50 requests por hora
- **storage_uri:** `memory://` - Almacenamiento en memoria (simple y rápido para desarrollo)
- **strategy:** `fixed-window` - Ventana fija de tiempo

### 3. Límites Específicos en Rutas Críticas

**Ubicación:** `auth.py`

#### Login - Protección contra Fuerza Bruta

```python
@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """Página de login con protección contra fuerza bruta"""
```

**Límite:** 5 intentos de login por minuto
**Objetivo:** Prevenir ataques de fuerza bruta de contraseñas

#### Registro - Prevención de Spam

```python
@auth_bp.route('/register', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per hour")
def register():
    """Registro de nuevos usuarios con rate limiting"""
```

**Límite:** 10 registros por hora
**Objetivo:** Prevenir creación masiva de cuentas

## Límites Configurados

### Tabla de Rate Limits

| Ruta | Límite Específico | Límite Global | Propósito |
|------|-------------------|---------------|-----------|
| `/auth/login` | 5 req/minuto | ✅ | Protección contra fuerza bruta |
| `/auth/register` | 10 req/hora | ✅ | Prevenir spam de cuentas |
| Todas las demás rutas | - | 200/día, 50/hora | Protección general |

### Respuesta al Exceder Límites

Cuando un cliente excede un límite, Flask-Limiter responde con:

**HTTP Status:** `429 Too Many Requests`

**Headers:**
```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1642345678
Retry-After: 60
```

**Body:** HTML por defecto con mensaje "Too Many Requests"

## Estrategias de Rate Limiting

### Fixed Window (Implementada)

**Funcionamiento:**
- Ventana de tiempo fija (ej: 1 minuto exacto)
- Contador se resetea al inicio de cada ventana
- Simple y eficiente

**Ejemplo:**
```
10:00:00 - 10:00:59 : 5 requests permitidos
10:01:00 - 10:01:59 : Contador resetea, 5 nuevos requests
```

**Ventajas:**
- Muy rápido
- Bajo uso de memoria
- Fácil de entender

**Desventaja:**
- Posible "burst" al cambio de ventana

### Alternativas Disponibles

Flask-Limiter soporta otras estrategias:

1. **moving-window:** Ventana deslizante (más preciso, más costoso)
2. **fixed-window-elastic-expiry:** Híbrido con expiración elástica

Para cambiar estrategia:
```python
limiter = Limiter(
    strategy="moving-window"  # Cambiar aquí
)
```

## Storage Backends

### Memory (Implementado)

**Configuración actual:** `storage_uri="memory://"`

**Características:**
- ✅ Muy rápido
- ✅ Sin dependencias externas
- ❌ No persiste entre reinicios
- ❌ No funciona con múltiples workers/servidores

**Ideal para:**
- Desarrollo
- Single-server deployments
- Aplicaciones pequeñas

### Redis (Recomendado para Producción)

Para producción con múltiples servers:

```python
limiter = Limiter(
    storage_uri="redis://localhost:6379"
)
```

**Ventajas:**
- Compartido entre múltiples instancias
- Persiste límites entre reinicios
- Alta performance

**Instalación:**
```bash
pip install redis
```

### Memcached

Alternativa a Redis:

```python
limiter = Limiter(
    storage_uri="memcached://localhost:11211"
)
```

## Casos de Uso

### Caso 1: Ataque de Fuerza Bruta

**Escenario:** Atacante intenta adivinar contraseñas

**Sin Rate Limiting:**
- 1000 intentos por minuto
- Contraseñas débiles comprometidas en segundos

**Con Rate Limiting (5/min):**
- 5 intentos por minuto
- 1000 intentos = 200 minutos (3.3 horas)
- Tiempo suficiente para detectar y bloquear IP

### Caso 2: Usuario Legítimo Olvida Contraseña

**Escenario:** Usuario intenta varias contraseñas incorrectas

**Resultado:**
- Primeros 5 intentos permitidos
- Después de 5, debe esperar 1 minuto
- Mensaje: "429 Too Many Requests"
- Usuario busca opción "Olvidé mi contraseña"

**Impacto:** Mínimo para usuarios legítimos, máxima protección

### Caso 3: Scraping Automatizado

**Escenario:** Bot intenta scrappear datos

**Sin Rate Limiting:**
- 1000s de requests por minuto
- Sobrecarga del servidor
- Costos de bandwidth elevados

**Con Rate Limiting (200/día, 50/hora):**
- Bot bloqueado rápidamente
- Servidor protegido
- Usuarios legítimos no afectados

## Personalización Avanzada

### Límites por Usuario Autenticado

Para aplicar límites por usuario en lugar de por IP:

```python
def get_user_id():
    if current_user.is_authenticated:
        return str(current_user.id)
    return get_remote_address()

limiter = Limiter(key_func=get_user_id)
```

### Excepciones para Administradores

```python
@app.route('/api/data')
@limiter.limit("100/hour", exempt_when=lambda: current_user.is_admin())
def api_data():
    ...
```

### Límites Dinámicos

```python
def dynamic_limit():
    if current_user.is_authenticated:
        if current_user.is_admin():
            return "1000/hour"
        return "100/hour"
    return "10/hour"

@app.route('/api/endpoint')
@limiter.limit(dynamic_limit)
def endpoint():
    ...
```

### Múltiples Límites

```python
@app.route('/api/expensive')
@limiter.limit("5 per minute")
@limiter.limit("50 per hour")
@limiter.limit("200 per day")
def expensive_operation():
    # Se aplica el límite más restrictivo alcanzado primero
    ...
```

## Monitoreo y Métricas

### Headers de Rate Limit

Cada respuesta incluye headers informativos:

```python
X-RateLimit-Limit: 50        # Límite total
X-RateLimit-Remaining: 45     # Requests restantes
X-RateLimit-Reset: 1642345678 # Timestamp de reset
```

### Logging de Excesos

Para registrar cuando se exceden límites:

```python
@app.errorhandler(429)
def ratelimit_handler(e):
    import logging
    logging.warning(f"Rate limit exceeded: {request.remote_addr} on {request.endpoint}")
    return "Too many requests", 429
```

### Métricas con Prometheus (Futuro)

```python
from prometheus_flask_exporter import PrometheusMetrics

metrics = PrometheusMetrics(app)
# Automáticamente expone métricas de rate limiting
```

## Testing de Rate Limiting

### Test Manual con cURL

```bash
# Hacer 6 requests rápidos al login
for i in {1..6}; do
  curl -X POST http://localhost:5000/auth/login \
    -d "username=test&password=test" \
    -w "\nStatus: %{http_code}\n"
done
```

**Resultado esperado:**
- Requests 1-5: `200 OK` o `302 Redirect`
- Request 6: `429 Too Many Requests`

### Test Automatizado

```python
import requests
import time

url = "http://localhost:5000/auth/login"
data = {"username": "test", "password": "test"}

# Hacer 6 requests
for i in range(6):
    response = requests.post(url, data=data)
    print(f"Request {i+1}: {response.status_code}")
    
    if i == 4:  # Después del 5to request
        assert response.status_code in [200, 302]
    elif i == 5:  # 6to request
        assert response.status_code == 429
        print(f"Rate limited! Retry after: {response.headers.get('Retry-After')}")
```

### Test de Headers

```python
response = requests.get("http://localhost:5000/")
print(f"Limit: {response.headers.get('X-RateLimit-Limit')}")
print(f"Remaining: {response.headers.get('X-RateLimit-Remaining')}")
print(f"Reset: {response.headers.get('X-RateLimit-Reset')}")
```

## Configuración de Producción

### 1. Usar Redis

```python
# config.py
class ProductionConfig(Config):
    RATELIMIT_STORAGE_URI = "redis://localhost:6379"
```

```python
# extensions.py
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=app.config.get('RATELIMIT_STORAGE_URI', 'memory://')
)
```

### 2. Ajustar Límites

Para aplicación en producción:

```python
# Más restrictivo
default_limits=["500 per day", "100 per hour"]

# Login más estricto
@limiter.limit("3 per minute")  # En vez de 5
```

### 3. Configurar Whitelist

IPs confiables sin límites:

```python
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day"],
    # IPs whitelistadas (localhost, load balancer, etc)
    headers_enabled=True
)

@app.before_request
def check_whitelist():
    whitelist = ['127.0.0.1', '10.0.0.1']
    if request.remote_addr in whitelist:
        g._bypass_rate_limit = True
```

### 4. Detrás de Proxy/Load Balancer

Si la app está detrás de nginx o similar:

```python
from flask_limiter.util import get_remote_address

def get_real_ip():
    # Usar X-Forwarded-For header
    return request.headers.get('X-Forwarded-For', request.remote_addr)

limiter = Limiter(key_func=get_real_ip)
```

## Beneficios Implementados

### Seguridad
- ✅ Protección contra fuerza bruta en login
- ✅ Prevención de spam en registro
- ✅ Límites globales contra abuso general

### Performance
- ✅ Previene sobrecarga del servidor
- ✅ Distribuye carga equitativamente
- ✅ Protege recursos del sistema

### Costos
- ✅ Reduce bandwidth consumido por bots
- ✅ Previene costos por abuso de API
- ✅ Optimiza uso de recursos

### Compliance
- ✅ Demuestra controles de seguridad
- ✅ Logs de intentos excesivos
- ✅ Protección de datos de usuarios

## Próximos Pasos

### Fase 2.4: Performance Optimization
1. Implementar paginación (20 items por página)
2. Agregar Flask-Caching
3. Optimizar queries con eager loading
4. Agregar índices de base de datos

### Mejoras Futuras de Rate Limiting
1. Migrar a Redis para producción
2. Implementar whitelist de IPs
3. Rate limits por usuario autenticado
4. Dashboard de métricas de límites
5. Alertas cuando IPs exceden límites repetidamente

## Referencias

- [Flask-Limiter Documentation](https://flask-limiter.readthedocs.io/)
- [ETAPA2_PLAN.md](ETAPA2_PLAN.md) - Plan completo de Stage 2
- [extensions.py](extensions.py) - Configuración de limiter
- [auth.py](auth.py) - Aplicación de límites

---

**Fase 2.3 Completada ✅**  
Rate limiting implementado y funcional. Aplicación protegida contra fuerza bruta y abuso.
