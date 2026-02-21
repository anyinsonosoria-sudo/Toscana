"""
Apartments Module
=================
Gestión de apartamentos y residentes.
Usa context managers para conexiones seguras a BD.
"""
from typing import List, Dict, Optional
import logging
from db import get_db

logger = logging.getLogger(__name__)


def add_apartment(number: str, floor: Optional[str] = None, notes: Optional[str] = None, 
                 resident_name: Optional[str] = None, resident_role: str = 'tenant',
                 resident_email: Optional[str] = None, resident_phone: Optional[str] = None,
                 payment_terms: int = 30) -> int:
    """Crea un nuevo apartamento con información del residente"""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Verificar que el número no exista ya
        cur.execute("SELECT id FROM apartments WHERE number=?", (number,))
        existing = cur.fetchone()
        if existing:
            raise ValueError(f"Ya existe un apartamento con el número '{number}'")
        
        cur.execute("""INSERT INTO apartments(number, floor, notes, resident_name, resident_role, 
                                               resident_email, resident_phone, payment_terms) 
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (number, floor, notes, resident_name, resident_role, resident_email, 
                     resident_phone, payment_terms))
        conn.commit()
        return cur.lastrowid


def list_apartments() -> List[Dict]:
    """Lista todos los apartamentos con información del residente"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT id, number, floor, notes, created_at, 
                              resident_name, resident_role, resident_email, 
                              resident_phone, payment_terms 
                       FROM apartments ORDER BY number""")
        rows = cur.fetchall()
        result = [dict(r) for r in rows]
        # Agregar residentes adicionales de la tabla residents
        for apt in result:
            cur.execute(
                "SELECT id, name, role, email, phone FROM residents WHERE unit_id=? ORDER BY id",
                (apt['id'],)
            )
            apt['extra_residents'] = [dict(r) for r in cur.fetchall()]
        return result


def save_extra_residents(apartment_id: int, residents_list: list) -> None:
    """Guarda residentes adicionales de un apartamento (reemplaza los anteriores)"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM residents WHERE unit_id=?", (apartment_id,))
        for r in residents_list:
            if r.get('name'):
                cur.execute(
                    "INSERT INTO residents (unit_id, name, email, phone, role) VALUES (?, ?, ?, ?, ?)",
                    (apartment_id, r['name'], r.get('email', ''), r.get('phone', ''), r.get('role', 'tenant'))
                )
        conn.commit()


def get_apartment(apartment_id: int) -> Optional[Dict]:
    """Obtiene un apartamento por ID"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM apartments WHERE id=?", (apartment_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_apartment(apartment_id: int, **fields) -> None:
    """Actualiza campos de un apartamento"""
    if not fields:
        return
    
    # Whitelist de columnas permitidas
    ALLOWED_COLUMNS = {'number', 'floor', 'notes', 'resident_name', 'resident_role', 
                      'resident_email', 'resident_phone', 'payment_terms'}
    
    with get_db() as conn:
        cur = conn.cursor()
        
        # Si se está actualizando el número, verificar que no esté duplicado
        if 'number' in fields:
            cur.execute("SELECT id FROM apartments WHERE number=? AND id!=?", 
                       (fields['number'], apartment_id))
            existing = cur.fetchone()
            if existing:
                raise ValueError(f"Ya existe otro apartamento con el número '{fields['number']}'")
        
        keys = []
        vals = []
        for k, v in fields.items():
            if k not in ALLOWED_COLUMNS:
                raise ValueError(f"Columna '{k}' no permitida para actualización")
            keys.append(f"{k}=?")
            vals.append(v)
        
        vals.append(apartment_id)
        cur.execute(f"UPDATE apartments SET {', '.join(keys)} WHERE id=?", vals)
        conn.commit()


def delete_apartment(apartment_id: int) -> None:
    """Elimina un apartamento verificando dependencias"""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Verificar si hay residentes asignados a este apartamento
        cur.execute("SELECT COUNT(*) as count FROM residents WHERE unit_id=?", (apartment_id,))
        result = cur.fetchone()
        if result and result['count'] > 0:
            raise ValueError(f"No se puede eliminar el apartamento porque tiene {result['count']} residente(s) asignado(s)")
        
        cur.execute("DELETE FROM apartments WHERE id=?", (apartment_id,))
        conn.commit()
