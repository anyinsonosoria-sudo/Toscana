from typing import List, Dict, Optional
from db import get_conn

def check_apartment_owner(unit_id: Optional[int], exclude_resident_id: Optional[int] = None) -> Optional[Dict]:
    """
    Verifica si un apartamento ya tiene un propietario asignado.
    Retorna el residente propietario si existe, None si no.
    exclude_resident_id: ID de residente a excluir de la búsqueda (para ediciones)
    """
    if not unit_id:
        return None
    
    conn = get_conn()
    cur = conn.cursor()
    
    if exclude_resident_id:
        cur.execute("""
            SELECT id, name, role FROM residents 
            WHERE unit_id=? AND role='Propietario' AND id!=?
        """, (unit_id, exclude_resident_id))
    else:
        cur.execute("""
            SELECT id, name, role FROM residents 
            WHERE unit_id=? AND role='Propietario'
        """, (unit_id,))
    
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def add_resident(unit_id: Optional[int], name: str, role: str = "tenant", email: Optional[str] = None, phone: Optional[str] = None, role_other: Optional[str] = None, payment_terms: int = 30) -> int:
    """
    role: 'Propietario', 'Inquilino', or 'Otro'
    role_other: If role is 'Otro', this specifies the custom role
    unit_id can be None if not assigned yet
    payment_terms: Days for invoice due date
    """
    # Validar si se intenta asignar un propietario a un apartamento que ya tiene uno
    if unit_id and role == 'Propietario':
        existing_owner = check_apartment_owner(unit_id)
        if existing_owner:
            raise ValueError(f"El apartamento ya tiene un propietario asignado: {existing_owner['name']}")
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO residents(unit_id, name, role, role_other, email, phone, payment_terms) VALUES(?,?,?,?,?,?,?)",
                (unit_id, name, role, role_other, email, phone, payment_terms))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid

def list_residents(unit_id: Optional[int] = None) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    if unit_id is not None:
        cur.execute("""
            SELECT r.id, r.unit_id, r.name, r.role, r.role_other, r.email, r.phone, r.payment_terms, r.created_at,
                   a.number as apartment_number
            FROM residents r
            LEFT JOIN apartments a ON r.unit_id = a.id
            WHERE r.unit_id=? 
            ORDER BY r.name
        """, (unit_id,))
    else:
        cur.execute("""
            SELECT r.id, r.unit_id, r.name, r.role, r.role_other, r.email, r.phone, r.payment_terms, r.created_at,
                   a.number as apartment_number
            FROM residents r
            LEFT JOIN apartments a ON r.unit_id = a.id
            ORDER BY r.name
        """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_resident(resident_id: int) -> Optional[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM residents WHERE id=?", (resident_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_resident(resident_id: int, **fields) -> None:
    if not fields:
        return
    
    # Validar si se intenta cambiar el rol a Propietario o cambiar de apartamento siendo Propietario
    if 'unit_id' in fields or 'role' in fields:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT unit_id, role FROM residents WHERE id=?", (resident_id,))
        current = cur.fetchone()
        conn.close()
        
        if current:
            current_unit_id = current['unit_id']
            current_role = current['role']
            new_unit_id = fields.get('unit_id', current_unit_id)
            new_role = fields.get('role', current_role)
            
            # Si el nuevo rol es Propietario y el apartamento cambió o se está cambiando a Propietario
            if new_unit_id and new_role == 'Propietario':
                # Verificar si ya hay un propietario en ese apartamento (excluyendo el residente actual)
                existing_owner = check_apartment_owner(new_unit_id, exclude_resident_id=resident_id)
                if existing_owner:
                    raise ValueError(f"El apartamento ya tiene un propietario asignado: {existing_owner['name']}")
    
    keys = []
    vals = []
    for k, v in fields.items():
        keys.append(f"{k}=?")
        vals.append(v)
    vals.append(resident_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE residents SET {', '.join(keys)} WHERE id=?", vals)
    conn.commit()
    conn.close()

def delete_resident(resident_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM residents WHERE id=?", (resident_id,))
    conn.commit()
    conn.close()

def list_by_unit(unit_id: int) -> List[Dict]:
    return list_residents(unit_id)
