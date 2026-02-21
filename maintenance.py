from typing import List, Dict, Optional
from pathlib import Path
from db import get_conn

def add_service(name: str, description: str = "", cost: float = 0.0, recurring: bool = False,
                code: Optional[str] = None, service_type: Optional[str] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO services(code, name, description, cost, recurring, service_type) VALUES(?,?,?,?,?,?)",
                (code, name, description, float(cost), 1 if recurring else 0, service_type))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid

def list_services() -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, code, name, description, cost, recurring, service_type, created_at FROM services ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_service(service_id: int) -> Optional[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM services WHERE id=?", (service_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_service(service_id: int, **fields) -> None:
    if not fields: return
    keys = []
    vals = []
    for k,v in fields.items():
        keys.append(f"{k}=?")
        vals.append(v)
    vals.append(service_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE services SET {', '.join(keys)} WHERE id=?", vals)
    conn.commit()
    conn.close()

def schedule_maintenance(service_id: int, scheduled_date: str, notes: str = "", cost: Optional[float] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO maintenance_records(service_id, scheduled_date, notes, cost) VALUES(?,?,?,?)",
                (service_id, scheduled_date, notes, cost))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid

def list_maintenance_records(service_id: Optional[int] = None) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    if service_id:
        cur.execute("SELECT id, service_id, scheduled_date, performed_date, notes, cost, completed, created_at FROM maintenance_records WHERE service_id=? ORDER BY scheduled_date DESC", (service_id,))
    else:
        cur.execute("SELECT id, service_id, scheduled_date, performed_date, notes, cost, completed, created_at FROM maintenance_records ORDER BY scheduled_date DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_maintenance_completed(record_id: int, performed_date: Optional[str] = None, cost: Optional[float] = None) -> None:
    conn = get_conn()
    cur = conn.cursor()
    if performed_date and cost is not None:
        cur.execute("UPDATE maintenance_records SET completed=1, performed_date=?, cost=? WHERE id=?", (performed_date, cost, record_id))
    elif performed_date:
        cur.execute("UPDATE maintenance_records SET completed=1, performed_date=? WHERE id=?", (performed_date, record_id))
    elif cost is not None:
        cur.execute("UPDATE maintenance_records SET completed=1, cost=? WHERE id=?", (cost, record_id))
    else:
        cur.execute("UPDATE maintenance_records SET completed=1 WHERE id=?", (record_id,))
    conn.commit()
    conn.close()

def delete_service(service_id: int) -> None:
    """Elimina un servicio. Verifica si hay registros de mantenimiento asociados."""
    conn = get_conn()
    cur = conn.cursor()
    # Verificar si hay registros de mantenimiento asociados
    cur.execute("SELECT COUNT(*) as count FROM maintenance_records WHERE service_id=?", (service_id,))
    result = cur.fetchone()
    if result and result['count'] > 0:
        conn.close()
        raise ValueError(f"No se puede eliminar el servicio porque tiene {result['count']} registro(s) de mantenimiento asociado(s)")
    
    cur.execute("DELETE FROM services WHERE id=?", (service_id,))
    conn.commit()
    conn.close()
