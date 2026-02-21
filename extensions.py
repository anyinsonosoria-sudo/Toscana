"""
Flask Extensions
================
Centralización de todas las extensiones de Flask para evitar importaciones circulares.
"""

from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask import request, jsonify, redirect, url_for

# ==========================================
# FLASK-LOGIN
# ==========================================
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Por favor inicia sesión para acceder a esta página."
login_manager.login_message_category = "warning"

# ==========================================
# CSRF PROTECTION
# ==========================================
csrf = CSRFProtect()

# ==========================================
# RATE LIMITING
# ==========================================
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)

# ==========================================
# CACHING
# ==========================================
cache = Cache(
    config={
        'CACHE_TYPE': 'SimpleCache',
        'CACHE_DEFAULT_TIMEOUT': 300
    }
)


def init_extensions(app):
    """
    Inicializa todas las extensiones con la aplicación Flask.
    
    Args:
        app: Instancia de Flask
    """
    # Inicializar Flask-Login
    login_manager.init_app(app)
    # Usar una clase de usuario anónimo que provea métodos esperados por templates
    try:
        import user_model
        login_manager.anonymous_user = user_model.AnonymousUser
    except Exception:
        pass
    
    # Configurar handler para solicitudes no autenticadas
    @login_manager.unauthorized_handler
    def handle_unauthorized():
        """Handle unauthorized access for both regular requests and AJAX"""
        # Para solicitudes AJAX, devolver JSON
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': 'Por favor inicia sesión para acceder a esta página.'
            }), 401
        
        # Para solicitudes regulares, hacer redirect a login
        return redirect(url_for(login_manager.login_view))
    
    # Configurar user_loader
    @login_manager.user_loader
    def load_user(user_id):
        try:
            import user_model
            return user_model.get_user_by_id(int(user_id))
        except Exception as e:
            print(f"[WARNING] Error loading user: {e}")
            return None
    
    # Inicializar CSRF Protection
    try:
        csrf.init_app(app)
    except Exception as e:
        print(f"[WARNING] No se pudo configurar CSRF protection: {e}")
    
    # Inicializar Rate Limiting
    try:
        limiter.init_app(app)
        print("[OK] Rate limiting configurado: 200/dia, 50/hora")
    except Exception as e:
        print(f"[WARNING] No se pudo configurar rate limiting: {e}")
    
    # Inicializar Cache
    try:
        cache.init_app(app)
        print("[OK] Cache configurado: SimpleCache, timeout 5 minutos")
    except Exception as e:
        print(f"[WARNING] No se pudo configurar cache: {e}")
    
    print("[OK] Extensiones de Flask inicializadas correctamente")
