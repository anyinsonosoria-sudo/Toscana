"""
Permissions Module - Sistema de Permisos Granulares
Maneja permisos específicos por módulo y acción

NOTA: Usa db.get_conn() centralizado para conexión a BD
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional

# Añadir el directorio padre al path para importar db
sys.path.insert(0, str(Path(__file__).parent.parent))
import db


def get_conn():
    """Obtiene conexión centralizada a la base de datos.
    
    DEPRECATED: Usar db.get_conn() directamente.
    Esta función se mantiene por compatibilidad.
    """
    return db.get_conn()


# ==========================================
# GESTIÓN DE PERMISOS
# ==========================================

def get_all_permissions() -> List[Dict]:
    """
    Obtiene todos los permisos disponibles agrupados por módulo
    
    Returns:
        Lista de permisos con estructura: {id, name, module, action, description}
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, module, action, description
            FROM permissions
            ORDER BY module, action
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_permissions_by_module() -> Dict[str, List[Dict]]:
    """
    Obtiene permisos agrupados por módulo
    
    Returns:
        Diccionario con módulos como keys y listas de permisos como values
    """
    permissions = get_all_permissions()
    grouped = {}
    
    for perm in permissions:
        module = perm['module']
        if module not in grouped:
            grouped[module] = []
        grouped[module].append(perm)
    
    return grouped


def get_user_permissions(user_id: int) -> List[str]:
    """
    Obtiene lista de nombres de permisos que tiene un usuario
    
    Args:
        user_id: ID del usuario
        
    Returns:
        Lista de nombres de permisos (ej: ['apartamentos.view', 'apartamentos.create'])
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.name
            FROM permissions p
            INNER JOIN user_permissions up ON p.id = up.permission_id
            WHERE up.user_id = ?
        """, (user_id,))
        return [row['name'] for row in cur.fetchall()]
    finally:
        conn.close()


def user_has_permission(user_id: int, permission_name: str) -> bool:
    """
    Verifica si un usuario tiene un permiso específico
    
    Args:
        user_id: ID del usuario
        permission_name: Nombre del permiso (ej: 'apartamentos.create')
        
    Returns:
        True si tiene el permiso, False si no
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as count
            FROM user_permissions up
            INNER JOIN permissions p ON up.permission_id = p.id
            WHERE up.user_id = ? AND p.name = ?
        """, (user_id, permission_name))
        result_row = cur.fetchone()
        return dict(result_row)['count'] > 0
    finally:
        conn.close()


def grant_permission(user_id: int, permission_name: str, granted_by: int = None) -> bool:
    """
    Otorga un permiso a un usuario
    
    Args:
        user_id: ID del usuario
        permission_name: Nombre del permiso
        granted_by: ID del usuario que otorga el permiso
        
    Returns:
        True si se otorgó exitosamente
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        
        # Obtener ID del permiso
        cur.execute("SELECT id FROM permissions WHERE name = ?", (permission_name,))
        perm_row = cur.fetchone()
        
        if not perm_row:
            raise ValueError(f"Permiso '{permission_name}' no existe")
        
        permission_id = perm_row['id']
        
        # Insertar relación (ON CONFLICT IGNORE si ya existe)
        cur.execute("""
            INSERT OR IGNORE INTO user_permissions (user_id, permission_id, granted_by)
            VALUES (?, ?, ?)
        """, (user_id, permission_id, granted_by))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def revoke_permission(user_id: int, permission_name: str) -> bool:
    """
    Revoca un permiso de un usuario
    
    Args:
        user_id: ID del usuario
        permission_name: Nombre del permiso
        
    Returns:
        True si se revocó exitosamente
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM user_permissions
            WHERE user_id = ? AND permission_id = (
                SELECT id FROM permissions WHERE name = ?
            )
        """, (user_id, permission_name))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def set_user_permissions(user_id: int, permission_names: List[str], granted_by: int = None):
    """
    Establece los permisos de un usuario (reemplaza permisos existentes)
    
    Args:
        user_id: ID del usuario
        permission_names: Lista de nombres de permisos
        granted_by: ID del usuario que otorga los permisos
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        
        # Eliminar permisos existentes
        cur.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
        
        # Insertar nuevos permisos
        for perm_name in permission_names:
            cur.execute("""
                INSERT INTO user_permissions (user_id, permission_id, granted_by)
                SELECT ?, id, ? FROM permissions WHERE name = ?
            """, (user_id, granted_by, perm_name))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_module_permissions(user_id: int, module: str) -> List[str]:
    """
    Obtiene los permisos de un usuario para un módulo específico
    
    Args:
        user_id: ID del usuario
        module: Nombre del módulo
        
    Returns:
        Lista de acciones permitidas (ej: ['view', 'create', 'edit'])
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.action
            FROM permissions p
            INNER JOIN user_permissions up ON p.id = up.permission_id
            WHERE up.user_id = ? AND p.module = ?
        """, (user_id, module))
        return [row['action'] for row in cur.fetchall()]
    finally:
        conn.close()


def grant_all_permissions(user_id: int, granted_by: int = None):
    """
    Otorga TODOS los permisos a un usuario (útil para operators por defecto)
    
    Args:
        user_id: ID del usuario
        granted_by: ID del usuario que otorga los permisos
    """
    all_perms = get_all_permissions()
    perm_names = [p['name'] for p in all_perms]
    set_user_permissions(user_id, perm_names, granted_by)


def revoke_all_permissions(user_id: int):
    """
    Revoca TODOS los permisos de un usuario
    
    Args:
        user_id: ID del usuario
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


# ==========================================
# HELPERS PARA DECORADORES
# ==========================================

def check_permission(user_id: int, permission_name: str, user_role: str = None) -> bool:
    """
    Verifica si un usuario puede realizar una acción
    Admin siempre puede todo
    
    Args:
        user_id: ID del usuario
        permission_name: Nombre del permiso a verificar
        user_role: Rol del usuario (opcional, para optimizar)
        
    Returns:
        True si tiene permiso
    """
    # Admin siempre tiene permiso
    if user_role == 'admin':
        return True
    
    return user_has_permission(user_id, permission_name)


# ==========================================
# UTILIDADES
# ==========================================

def get_permissions_summary(user_id: int) -> Dict[str, Dict[str, bool]]:
    """
    Obtiene un resumen de permisos del usuario agrupado por módulo
    
    Args:
        user_id: ID del usuario
        
    Returns:
        Dict con estructura: {
            'apartamentos': {'view': True, 'create': True, 'edit': False, 'delete': False},
            'facturacion': {...}
        }
    """
    user_perms = get_user_permissions(user_id)
    all_perms = get_permissions_by_module()
    
    summary = {}
    for module, perms in all_perms.items():
        summary[module] = {}
        for perm in perms:
            summary[module][perm['action']] = perm['name'] in user_perms
    
    return summary
