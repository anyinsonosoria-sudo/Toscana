from typing import List, Dict, Optional
from db import get_conn

def add_product_service(name: str, type: str, price: float, code: Optional[str] = None, 
                        description: Optional[str] = None, additional_notes: Optional[str] = None, 
                        active: int = 1) -> int:
    """Add a new product or service"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Si se proporciona un código, verificar que no exista
    if code:
        cur.execute("SELECT id FROM products_services WHERE code=?", (code,))
        existing = cur.fetchone()
        if existing:
            conn.close()
            raise ValueError(f"Ya existe un producto/servicio con el código '{code}'")
    
    cur.execute("""INSERT INTO products_services(code, name, type, description, additional_notes, price, active) 
                   VALUES(?,?,?,?,?,?,?)""",
                (code, name, type, description, additional_notes, price, active))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid

def list_products_services(active_only: bool = False) -> List[Dict]:
    """List all products and services"""
    conn = get_conn()
    cur = conn.cursor()
    if active_only:
        cur.execute("""SELECT id, code, name, type, description, additional_notes, price, active, created_at 
                       FROM products_services WHERE active = 1 ORDER BY name""")
    else:
        cur.execute("""SELECT id, code, name, type, description, additional_notes, price, active, created_at 
                       FROM products_services ORDER BY name""")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_product_service(item_id: int) -> Optional[Dict]:
    """Get a single product or service by ID"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products_services WHERE id=?", (item_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_product_service(item_id: int, **fields) -> None:
    """Update a product or service with given fields"""
    if not fields:
        return
    
    # Si se está actualizando el código, verificar que no esté duplicado
    if 'code' in fields and fields['code']:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM products_services WHERE code=? AND id!=?", (fields['code'], item_id))
        existing = cur.fetchone()
        if existing:
            conn.close()
            raise ValueError(f"Ya existe otro producto/servicio con el código '{fields['code']}'")
        conn.close()
    
    keys = []
    vals = []
    for k, v in fields.items():
        keys.append(f"{k}=?")
        vals.append(v)
    vals.append(item_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE products_services SET {', '.join(keys)} WHERE id=?", vals)
    conn.commit()
    conn.close()

def delete_product_service(item_id: int) -> None:
    """Delete a product or service"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM products_services WHERE id=?", (item_id,))
    conn.commit()
    conn.close()

def find_by_code(code: str) -> Optional[Dict]:
    """Find a product or service by code"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products_services WHERE code=? AND active=1", (code,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def search_products_services(query: Optional[str] = None, active_only: bool = True) -> List[Dict]:
    """Search products/services by code, name, or description. Returns all if query is empty."""
    conn = get_conn()
    cur = conn.cursor()
    
    if query:
        # Search by code, name, or description
        search_pattern = f"%{query}%"
        if active_only:
            cur.execute("""
                SELECT id, code, name, type, description, price, active 
                FROM products_services 
                WHERE active=1 AND (code LIKE ? OR name LIKE ? OR description LIKE ?)
                ORDER BY name
            """, (search_pattern, search_pattern, search_pattern))
        else:
            cur.execute("""
                SELECT id, code, name, type, description, price, active 
                FROM products_services 
                WHERE code LIKE ? OR name LIKE ? OR description LIKE ?
                ORDER BY name
            """, (search_pattern, search_pattern, search_pattern))
    else:
        # Return all
        if active_only:
            cur.execute("""
                SELECT id, code, name, type, description, price, active 
                FROM products_services 
                WHERE active=1
                ORDER BY name
            """)
        else:
            cur.execute("""
                SELECT id, code, name, type, description, price, active 
                FROM products_services 
                ORDER BY name
            """)
    
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
