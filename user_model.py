"""
User Model - Sistema de Autenticación
Maneja usuarios, roles y autenticación del sistema

NOTA: Usa db.get_conn() centralizado para conexión a BD
"""

from datetime import datetime
from flask_login import UserMixin, AnonymousUserMixin
import bcrypt

# Usar conexión centralizada de db.py
import db


class User(UserMixin):
    """
    Modelo de Usuario compatible con Flask-Login
    """
    
    def __init__(self, id, username, email, password_hash, full_name, role, is_active, created_at, last_login):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.full_name = full_name
        self.role = role
        self._is_active = bool(is_active)  # Usar atributo privado
        self.created_at = created_at
        self.last_login = last_login
    
    def check_password(self, password):
        """Verifica la contraseña"""
        if not self.password_hash:
            return False
        # Convertir a bytes si es necesario
        password_bytes = password.encode('utf-8') if isinstance(password, str) else password
        hash_bytes = self.password_hash.encode('utf-8') if isinstance(self.password_hash, str) else self.password_hash
        return bcrypt.checkpw(password_bytes, hash_bytes)
    
    def set_password(self, password):
        """Establece una nueva contraseña hasheada"""
        password_bytes = password.encode('utf-8') if isinstance(password, str) else password
        salt = bcrypt.gensalt()
        hash_bytes = bcrypt.hashpw(password_bytes, salt)
        self.password_hash = hash_bytes.decode('utf-8')
    
    def is_admin(self):
        """Verifica si el usuario es administrador"""
        return self.role == 'admin'
    
    def is_operator(self):
        """Verifica si el usuario es operador"""
        return self.role == 'operator'
    
    def is_resident(self):
        """Verifica si el usuario es residente"""
        return self.role == 'resident'
    
    def get_id(self):
        """Requerido por Flask-Login"""
        return str(self.id)
    
    @property
    def is_active(self):
        """Requerido por Flask-Login - indica si el usuario está activo"""
        return self._is_active
    
    @property
    def is_authenticated(self):
        """Requerido por Flask-Login"""
        return True
    
    @property
    def is_anonymous(self):
        """Requerido por Flask-Login"""
        return False
    
    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


# ==========================================
# FUNCIONES DE GESTIÓN DE USUARIOS
# ==========================================

def get_conn():
    """Obtiene conexión centralizada a la base de datos.
    
    DEPRECATED: Usar db.get_conn() directamente.
    Esta función se mantiene por compatibilidad.
    """
    return db.get_conn()


def get_user_by_id(user_id):
    """
    Obtiene un usuario por ID
    
    Args:
        user_id: ID del usuario
        
    Returns:
        User object o None
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, email, password_hash, full_name, role, is_active, created_at, last_login
            FROM users 
            WHERE id = ?
        """, (user_id,))
        
        row = cur.fetchone()
        if row:
            return User(
                id=row['id'],
                username=row['username'],
                email=row['email'],
                password_hash=row['password_hash'],
                full_name=row['full_name'],
                role=row['role'],
                is_active=row['is_active'],
                created_at=row['created_at'],
                last_login=row['last_login']
            )
        return None
    finally:
        conn.close()


def get_user_by_username(username):
    """
    Obtiene un usuario por nombre de usuario
    
    Args:
        username: Nombre de usuario
        
    Returns:
        User object o None
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, email, password_hash, full_name, role, is_active, created_at, last_login
            FROM users 
            WHERE username = ?
        """, (username,))
        
        row = cur.fetchone()
        if row:
            return User(
                id=row['id'],
                username=row['username'],
                email=row['email'],
                password_hash=row['password_hash'],
                full_name=row['full_name'],
                role=row['role'],
                is_active=row['is_active'],
                created_at=row['created_at'],
                last_login=row['last_login']
            )
        return None
    finally:
        conn.close()


def get_user_by_email(email):
    """
    Obtiene un usuario por email
    
    Args:
        email: Email del usuario
        
    Returns:
        User object o None
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, email, password_hash, full_name, role, is_active, created_at, last_login
            FROM users 
            WHERE email = ?
        """, (email,))
        
        row = cur.fetchone()
        if row:
            return User(
                id=row['id'],
                username=row['username'],
                email=row['email'],
                password_hash=row['password_hash'],
                full_name=row['full_name'],
                role=row['role'],
                is_active=row['is_active'],
                created_at=row['created_at'],
                last_login=row['last_login']
            )
        return None
    finally:
        conn.close()


def create_user(username, email, password, full_name, role='operator'):
    """
    Crea un nuevo usuario
    
    Args:
        username: Nombre de usuario (único)
        email: Email (único)
        password: Contraseña en texto plano (se hasheará)
        full_name: Nombre completo
        role: Rol del usuario (admin, operator, resident)
        
    Returns:
        ID del usuario creado o None si hay error
    """
    conn = get_conn()
    try:
        # Verificar si ya existe
        if get_user_by_username(username):
            raise ValueError(f"El usuario '{username}' ya existe")
        
        if get_user_by_email(email):
            raise ValueError(f"El email '{email}' ya está registrado")
        
        # Hashear contraseña con bcrypt
        password_bytes = password.encode('utf-8') if isinstance(password, str) else password
        salt = bcrypt.gensalt()
        hash_bytes = bcrypt.hashpw(password_bytes, salt)
        password_hash = hash_bytes.decode('utf-8')
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (username, email, password_hash, full_name, role, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (username, email, password_hash, full_name, role))
        
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def update_last_login(user_id):
    """
    Actualiza la fecha del último login
    
    Args:
        user_id: ID del usuario
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE users 
            SET last_login = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user_id,))
        conn.commit()
    finally:
        conn.close()


def update_password(user_id, new_password):
    """
    Actualiza la contraseña de un usuario
    
    Args:
        user_id: ID del usuario
        new_password: Nueva contraseña en texto plano
    """
    conn = get_conn()
    try:
        # Hashear nueva contraseña con bcrypt
        password_bytes = new_password.encode('utf-8') if isinstance(new_password, str) else new_password
        salt = bcrypt.gensalt()
        hash_bytes = bcrypt.hashpw(password_bytes, salt)
        password_hash = hash_bytes.decode('utf-8')
        
        cur = conn.cursor()
        cur.execute("""
            UPDATE users 
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (password_hash, user_id))
        conn.commit()
    finally:
        conn.close()


def list_users():
    """
    Lista todos los usuarios
    
    Returns:
        Lista de diccionarios con información de usuarios (sin password_hash)
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, email, full_name, role, is_active, created_at, last_login
            FROM users
            ORDER BY created_at DESC
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def deactivate_user(user_id):
    """
    Desactiva un usuario (soft delete)
    
    Args:
        user_id: ID del usuario
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE users 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user_id,))
        conn.commit()
    finally:
        conn.close()


def activate_user(user_id):
    """
    Activa un usuario desactivado
    
    Args:
        user_id: ID del usuario
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE users 
            SET is_active = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user_id,))
        conn.commit()
    finally:
        conn.close()
