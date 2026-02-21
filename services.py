"""
Módulo de Servicios y Productos
Gestión independiente de servicios/productos para facturación y ventas
Separado del módulo de mantenimiento
"""

from typing import List, Dict, Optional
from db import get_conn
from pathlib import Path
Eliminado: gestión de servicios ahora es solo por products_services/configuracion
        query += " ORDER BY name"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        
        return [dict(r) for r in rows]
    except Exception as e:
        _log(f"Error in list_services: {e}")
        return []

def get_service(service_id: int) -> Optional[Dict]:
    """Obtener un servicio/producto por ID"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, description, cost as price, type, category, active FROM services WHERE id=?", (service_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        _log(f"Error in get_service: {e}")
        return None

def find_by_code(code: str) -> Optional[Dict]:
    """Buscar servicio por código"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, description, cost as price, type, category, active FROM services WHERE code=?", (code,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        _log(f"Error in find_by_code: {e}")
        return None

def search_services(query: Optional[str] = None, active_only: bool = True) -> List[Dict]:
    """Buscar servicios por nombre o descripción"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        if not query:
            return list_services(active_only=active_only)
        
        search_term = f"%{query}%"
        sql = """
            SELECT id, code, name, description, cost as price, type, category, active FROM services 
            WHERE (name LIKE ? OR description LIKE ? OR code LIKE ?)
        """
        params = [search_term, search_term, search_term]
        
        if active_only:
            sql += " AND active = 1"
        
        sql += " ORDER BY name"
        
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        
        return [dict(r) for r in rows]
    except Exception as e:
        _log(f"Error in search_services: {e}")
        return []

def update_service(service_id: int, **fields) -> bool:
    """Actualizar servicio/producto"""
    if not fields:
        return False
    
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Agregar timestamp de actualización
        fields['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        keys = [f"{k}=?" for k in fields.keys()]
        vals = list(fields.values())
        vals.append(service_id)
        
        cur.execute(f"UPDATE services SET {', '.join(keys)} WHERE id=?", vals)
        conn.commit()
        conn.close()
        
        _log(f"Servicio actualizado: ID {service_id}")
        return True
    except Exception as e:
        _log(f"Error in update_service: {e}")
        return False

def delete_service(service_id: int) -> bool:
    """Eliminar servicio/producto (soft delete)"""
    try:
        return update_service(service_id, active=0)
    except Exception as e:
        _log(f"Error in delete_service: {e}")
        return False

def toggle_service_active(service_id: int) -> bool:
    """Alternar estado activo/inactivo de un servicio"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Obtener estado actual
        cur.execute("SELECT active FROM services WHERE id=?", (service_id,))
        row = cur.fetchone()
        
        if not row:
            conn.close()
            return False
        
        current_active = dict(row)['active']
        new_active = 1 - current_active
        
        cur.execute("UPDATE services SET active=?, updated_at=? WHERE id=?",
                   (new_active, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), service_id))
        conn.commit()
        conn.close()
        
        _log(f"Servicio {service_id} estado cambiado a: {new_active}")
        return True
    except Exception as e:
        _log(f"Error in toggle_service_active: {e}")
        return False

def get_service_stats() -> Dict:
    """Obtener estadísticas de servicios"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Total de servicios
        cur.execute("SELECT COUNT(*) as total FROM services")
        total = dict(cur.fetchone())['total']
        
        # Activos
        cur.execute("SELECT COUNT(*) as active FROM services WHERE active=1")
        active = dict(cur.fetchone())['active']
        
        # Por tipo
        cur.execute("SELECT type, COUNT(*) as count FROM services GROUP BY type")
        by_type = {dict(row)['type']: dict(row)['count'] for row in cur.fetchall()}
        
        # Precio promedio
        cur.execute("SELECT AVG(cost) as avg_price FROM services WHERE active=1")
        avg_price = dict(cur.fetchone())['avg_price'] or 0
        
        conn.close()
        
        return {
            'total': total,
            'active': active,
            'inactive': total - active,
            'by_type': by_type,
            'average_price': round(avg_price, 2)
        }
    except Exception as e:
        _log(f"Error in get_service_stats: {e}")
        return {}

def get_services_by_category(category: str) -> List[Dict]:
    """Obtener servicios por categoría"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, code, name, description, cost as price, type, category, active FROM services
            WHERE category=? AND active=1 
            ORDER BY name
        """, (category,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        _log(f"Error in get_services_by_category: {e}")
        return []

def get_all_categories() -> List[str]:
    """Obtener todas las categorías disponibles"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT category FROM services WHERE category IS NOT NULL ORDER BY category")
        rows = cur.fetchall()
        conn.close()
        return [dict(r)['category'] for r in rows]
    except Exception as e:
        _log(f"Error in get_all_categories: {e}")
        return []

# Inicializar tabla al importar el módulo
try:
    create_services_table()
except Exception as e:
    _log(f"Warning: Could not initialize services_products table: {e}")
