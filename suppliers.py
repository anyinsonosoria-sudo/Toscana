from typing import List, Dict, Optional
from db import get_conn

def add_supplier(name: str, supplier_type: Optional[str] = None, supplier_type_other: Optional[str] = None,
                 contact_name: Optional[str] = None, email: Optional[str] = None, 
                 phone: Optional[str] = None, address: Optional[str] = None, 
                 tax_id: Optional[str] = None, payment_terms: int = 30) -> int:
    """Add a new supplier"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""INSERT INTO suppliers(name, supplier_type, supplier_type_other, contact_name, email, phone, address, tax_id, payment_terms) 
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (name, supplier_type, supplier_type_other, contact_name, email, phone, address, tax_id, payment_terms))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid

def list_suppliers() -> List[Dict]:
    """List all suppliers"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""SELECT id, name, supplier_type, supplier_type_other, contact_name, email, phone, address, tax_id, payment_terms, created_at 
                   FROM suppliers ORDER BY name""")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_supplier(supplier_id: int) -> Optional[Dict]:
    """Get a single supplier by ID"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM suppliers WHERE id=?", (supplier_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_supplier(supplier_id: int, **fields) -> None:
    """Update a supplier with given fields"""
    if not fields:
        return
    
    # Whitelist de columnas permitidas
    ALLOWED_COLUMNS = {'name', 'supplier_type', 'supplier_type_other', 'contact_name', 
                      'email', 'phone', 'address', 'tax_id', 'payment_terms'}
    
    keys = []
    vals = []
    for k, v in fields.items():
        if k not in ALLOWED_COLUMNS:
            raise ValueError(f"Columna '{k}' no permitida para actualización")
        keys.append(f"{k}=?")
        vals.append(v)
    vals.append(supplier_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE suppliers SET {', '.join(keys)} WHERE id=?", vals)
    conn.commit()
    conn.close()

def delete_supplier(supplier_id: int) -> None:
    """Delete a supplier. Verifica si hay gastos asociados."""
    conn = get_conn()
    cur = conn.cursor()
    # Verificar si hay gastos asociados a este suplidor
    cur.execute("SELECT COUNT(*) as count FROM expenses WHERE supplier_id=?", (supplier_id,))
    result = cur.fetchone()
    if result and result['count'] > 0:
        conn.close()
        raise ValueError(f"No se puede eliminar el suplidor porque tiene {result['count']} gasto(s) asociado(s)")
    
    cur.execute("DELETE FROM suppliers WHERE id=?", (supplier_id,))
    conn.commit()
    conn.close()
