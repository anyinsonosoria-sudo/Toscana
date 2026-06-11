"""
User Model - Sistema de Autenticación
Maneja usuarios, roles y autenticación del sistema

Refactorizado para usar SQLAlchemy (ORM).
"""

from datetime import datetime, timezone
from flask_login import AnonymousUserMixin
from extensions import db
from data_models.models import User

class AnonymousUser(AnonymousUserMixin):
    """Usuario anónimo para Flask-Login.

    Provee atributos de rol que los templates esperan para que
    no fallen cuando el usuario no está autenticado.
    """

    @property
    def role(self):
        return None

    def is_admin(self):
        return False

    def is_operator(self):
        return False

    def is_resident(self):
        return False


# ==========================================
# FUNCIONES DE GESTIÓN DE USUARIOS (ORM wrapper)
# ==========================================

def get_user_by_id(user_id):
    """Obtiene un usuario por ID"""
    return db.session.get(User, user_id)

def get_user_by_username(username):
    """Obtiene un usuario por nombre de usuario"""
    return User.query.filter_by(username=username).first()

def get_user_by_email(email):
    """Obtiene un usuario por email"""
    return User.query.filter_by(email=email).first()

def create_user(username, email, password, full_name, role='operator'):
    """Crea un nuevo usuario (dual-write: ORM + legacy DB durante migración)"""
    if get_user_by_username(username):
        raise ValueError(f"El usuario '{username}' ya existe")
    
    if get_user_by_email(email):
        raise ValueError(f"El email '{email}' ya está registrado")
    
    new_user = User(
        username=username,
        email=email,
        full_name=full_name,
        role=role,
        is_active=True
    )
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()

    # Dual-write: sincronizar con BD legacy (sqlite3) para que
    # los módulos no migrados (residents, etc.) no fallen por FK.
    try:
        import db as legacy_db
        conn = legacy_db.get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO users "
            "(id, username, email, password_hash, full_name, role, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_user.id, new_user.username, new_user.email,
             new_user.password_hash, new_user.full_name, new_user.role, 1),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # No bloquear si la BD legacy falla

    return new_user.id

def update_last_login(user_id):
    """Actualiza la fecha del último login"""
    user = get_user_by_id(user_id)
    if user:
        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

def update_password(user_id, new_password):
    """Actualiza la contraseña de un usuario"""
    user = get_user_by_id(user_id)
    if user:
        user.set_password(new_password)
        db.session.commit()

def list_users():
    """Lista todos los usuarios (Retorna diccionarios para compatibilidad retroactiva)"""
    users = User.query.order_by(User.created_at.desc()).all()
    return [{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'full_name': u.full_name,
        'role': u.role,
        'is_active': u.is_active,
        'created_at': u.created_at.isoformat() if u.created_at else None,
        'last_login': u.last_login.isoformat() if u.last_login else None
    } for u in users]

def deactivate_user(user_id):
    """Desactiva un usuario (soft delete)"""
    user = get_user_by_id(user_id)
    if user:
        user.is_active = False
        db.session.commit()

def activate_user(user_id):
    """Activa un usuario desactivado"""
    user = get_user_by_id(user_id)
    if user:
        user.is_active = True
        db.session.commit()
