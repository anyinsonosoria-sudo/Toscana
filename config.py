"""
Configuration Module
====================
Gestión centralizada de configuración por entornos.

SECURITY NOTES:
- SECRET_KEY debe ser única y segura en producción
- Usar variables de entorno para credenciales sensibles
- Nunca commitear valores de producción al repositorio
"""

import os
import secrets
from pathlib import Path

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv no instalado. Usando variables de entorno del sistema.")


# ==========================================
# SECURITY: Lista de claves inseguras conocidas
# ==========================================
INSECURE_KEYS = frozenset([
    'dev-secret-change-in-production-INSECURE',
    'dev-secret-key-change-in-production',
    'secret',
    'password',
    'change-me',
    'your-secret-key',
    ''
])


def _generate_secure_key():
    """Genera una clave secreta segura para desarrollo."""
    return secrets.token_hex(32)


def _validate_secret_key(key: str, env: str) -> str:
    """
    Valida que la SECRET_KEY sea segura.
    
    Args:
        key: La clave a validar
        env: El entorno (development, production, testing)
        
    Returns:
        str: La clave validada
        
    Raises:
        ValueError: Si la clave es insegura en producción
    """
    if env == 'production':
        if not key or key in INSECURE_KEYS or len(key) < 32:
            raise ValueError(
                "\n" + "="*60 + "\n"
                "⚠️  ERROR DE SEGURIDAD CRÍTICO\n"
                "="*60 + "\n"
                "FLASK_SECRET_KEY debe estar definida en producción.\n"
                "La clave debe tener al menos 32 caracteres.\n\n"
                "Genera una clave segura con:\n"
                "  python -c \"import secrets; print(secrets.token_hex(32))\"\n\n"
                "Y configurala en tu .env o variables de entorno:\n"
                "  FLASK_SECRET_KEY=tu-clave-segura-aqui\n"
                "="*60
            )
    return key


def _env_bool(name: str, default: bool = False) -> bool:
    """Parsea un booleano desde entorno (1/true/yes)."""
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes")


class Config:
    """Configuración base"""
    
    # Directorio base de la aplicación
    BASE_DIR = Path(__file__).parent
    
    # ==========================================
    # SEGURIDAD
    # ==========================================
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", _generate_secure_key())
    
    # Protección CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # Sin límite de tiempo para tokens CSRF
    
    # ==========================================
    # SESIONES
    # ==========================================
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Permitir desactivar secure en desarrollo local sin tocar producción
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = int(os.getenv("PERMANENT_SESSION_LIFETIME", 3600))  # 1 hora
    
    # ==========================================
    # ARCHIVOS
    # ==========================================
    UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf"}
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_SIZE", 10485760))  # 10MB por defecto
    
    # ==========================================
    # BASE DE DATOS
    # ==========================================
    DATABASE_PATH = BASE_DIR / "data.db"
    
    # ==========================================
    # EMAIL (SMTP)
    # ==========================================
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "")
    SMTP_USE_TLS = True
    
    # ==========================================
    # TWILIO / SMS
    # ==========================================
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM = os.getenv("TWILIO_FROM", "")
    TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")
    
    # ==========================================
    # PAGINACIÓN
    # ==========================================
    ITEMS_PER_PAGE = 20
    
    # ==========================================
    # LOGGING
    # ==========================================
    LOG_FILE = BASE_DIR / "audit.log"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # ==========================================
    # SECURITY HEADERS (configurados en app.py)
    # ==========================================
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
    }


class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False  # HTTP permitido en desarrollo


class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", True)  # Solo HTTPS por defecto
    
    # Security Headers más estrictos para producción
    SECURITY_HEADERS = {
        **Config.SECURITY_HEADERS,
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; img-src 'self' data: blob:; font-src 'self' cdn.jsdelivr.net;"
    }
    
    def __init__(self):
        """Valida configuración de seguridad al inicializar."""
        super().__init__()
        _validate_secret_key(self.SECRET_KEY, 'production')


class TestingConfig(Config):
    """Configuración para testing"""
    TESTING = True
    WTF_CSRF_ENABLED = False  # Desactivar CSRF en tests
    DATABASE_PATH = ":memory:"  # Base de datos en memoria para tests


# Diccionario de configuraciones
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig
}


def get_config():
    """
    Obtiene la configuración según la variable de entorno FLASK_ENV.
    
    Returns:
        Config: Clase de configuración apropiada
    """
    env = os.getenv("FLASK_ENV", "development")
    return config_by_name.get(env, DevelopmentConfig)


# ==========================================
# HELPER FUNCTIONS (compatibilidad con código antiguo)
# ==========================================

def get_email_config():
    """Retorna configuración de email"""
    config = get_config()
    return {
        "host": config.SMTP_SERVER,
        "port": config.SMTP_PORT,
        "user": config.SMTP_USER,
        "password": config.SMTP_PASSWORD,
        "from": config.SMTP_FROM
    }


def get_twilio_config():
    """Retorna configuración de Twilio"""
    config = get_config()
    return {
        "sid": config.TWILIO_ACCOUNT_SID,
        "token": config.TWILIO_AUTH_TOKEN,
        "from": config.TWILIO_FROM,
        "whatsapp_from": config.TWILIO_WHATSAPP_FROM
    }


def is_email_configured():
    """Verifica si el email está configurado"""
    cfg = get_email_config()
    return bool(cfg["host"] and cfg["user"] and cfg["password"])


def is_sms_configured():
    """Verifica si SMS está configurado"""
    cfg = get_twilio_config()
    return bool(cfg["sid"] and cfg["token"] and cfg["from"])
