from typing import List, Dict, Optional
from db import get_conn
from datetime import datetime
import os
from pathlib import Path

def add_expense(description: str, amount: float, category: Optional[str] = None, 
                supplier_id: Optional[int] = None, date: Optional[str] = None,
                payment_method: Optional[str] = None, notes: Optional[str] = None,
                receipt_path: Optional[str] = None) -> int:
    """Add a new expense with optional receipt image"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""INSERT INTO expenses(description, amount, category, supplier_id, date, payment_method, notes, receipt_path) 
                   VALUES(?,?,?,?,?,?,?,?)""",
                (description, amount, category, supplier_id, date, payment_method, notes, receipt_path))
    conn.commit()
    rid = cur.lastrowid
    
    # Crear transacción de contabilidad (gasto)
    try:
        cur.execute("""
            INSERT INTO accounting_transactions(type, description, amount, category, reference, date)
            VALUES(?, ?, ?, ?, ?, ?)
        """, ('expense', f'Gasto: {description}', amount, category or 'General', f'EXP-{rid}', date))
        conn.commit()
    except Exception as e:
        # Log error pero no fallar el registro de gasto
        try:
            from models import _log
            _log(f"Error creating accounting transaction for expense {rid}: {e}")
        except:
            print(f"Error creating accounting transaction for expense {rid}: {e}")
    
    conn.close()
    return rid

def list_expenses() -> List[Dict]:
    """List all expenses with supplier information"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.id, e.description, e.amount, e.category, e.supplier_id, 
               e.date, e.payment_method, e.notes, e.created_at,
               s.name as supplier_name
        FROM expenses e
        LEFT JOIN suppliers s ON e.supplier_id = s.id
        ORDER BY e.date DESC, e.created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_expense(expense_id: int) -> Optional[Dict]:
    """Get a single expense by ID with receipt info"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.*, s.name as supplier_name
        FROM expenses e
        LEFT JOIN suppliers s ON e.supplier_id = s.id
        WHERE e.id=?
    """, (expense_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def save_receipt_image(file, expense_id: int) -> Optional[str]:
    """
    Guarda imagen de recibo en carpeta uploads
    
    Args:
        file: FileStorage object from Flask request or BytesIO object
        expense_id: ID del gasto
        
    Returns:
        Ruta relativa del archivo guardado o None si hay error
    """
    try:
        # Crear carpeta de uploads si no existe
        uploads_dir = Path("static/uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)
        
        # Generar nombre único
        filename = f"receipt_{expense_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = uploads_dir / filename
        
        # Guardar archivo (compatible con FileStorage y BytesIO)
        if hasattr(file, 'save'):
            # Es FileStorage
            file.save(str(filepath))
        else:
            # Es BytesIO u otro objeto con .read()
            with open(str(filepath), 'wb') as f:
                f.write(file.read() if hasattr(file, 'read') else file)
        
        # Retornar ruta relativa
        return f"static/uploads/{filename}"
    except Exception as e:
        print(f"Error guardando recibo: {e}")
        return None

def get_receipt_path(expense_id: int) -> Optional[str]:
    """Obtiene la ruta del recibo de un gasto"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT receipt_path FROM expenses WHERE id=?", (expense_id,))
    row = cur.fetchone()
    conn.close()
    return row['receipt_path'] if row else None

def update_expense(expense_id: int, **fields) -> None:
    """Update an expense with given fields and sync accounting transaction"""
    if not fields:
        return
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Obtener el gasto actual para sincronizar contabilidad
    cur.execute("SELECT * FROM expenses WHERE id=?", (expense_id,))
    old_expense = cur.fetchone()
    
    keys = []
    vals = []
    for k,v in fields.items():
        keys.append(f"{k}=?")
        vals.append(v)
    vals.append(expense_id)
    
    cur.execute(f"UPDATE expenses SET {', '.join(keys)} WHERE id=?", vals)
    
    # Actualizar transacción de contabilidad si existe
    try:
        # Buscar la transacción correspondiente
        cur.execute("""
            SELECT id FROM accounting_transactions 
            WHERE reference = ? AND type = 'expense'
        """, (f'EXP-{expense_id}',))
        
        txn = cur.fetchone()
        if txn:
            # Actualizar monto si cambió
            if 'amount' in fields:
                new_amount = fields['amount']
                cur.execute("""
                    UPDATE accounting_transactions SET amount = ? 
                    WHERE id = ?
                """, (new_amount, txn['id']))
            
            # Actualizar descripción si cambió
            if 'description' in fields or 'category' in fields:
                new_desc = fields.get('description', old_expense['description'] if old_expense else '')
                new_category = fields.get('category', old_expense['category'] if old_expense else 'General')
                cur.execute("""
                    UPDATE accounting_transactions SET description = ?, category = ? 
                    WHERE id = ?
                """, (f'Gasto: {new_desc}', new_category or 'General', txn['id']))
            
            # Actualizar fecha si cambió
            if 'date' in fields:
                cur.execute("""
                    UPDATE accounting_transactions SET date = ? 
                    WHERE id = ?
                """, (fields['date'], txn['id']))
    except Exception as e:
        print(f"Error updating accounting transaction for expense {expense_id}: {e}")
    
    conn.commit()
    conn.close()

def delete_expense(expense_id: int) -> None:
    """Delete an expense and its corresponding accounting transaction"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Eliminar la transacción de contabilidad asociada
    try:
        cur.execute("""
            DELETE FROM accounting_transactions 
            WHERE reference = ? AND type = 'expense'
        """, (f'EXP-{expense_id}',))
    except Exception as e:
        print(f"Error deleting accounting transaction for expense {expense_id}: {e}")
    
    # Eliminar el gasto
    cur.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    conn.close()

def get_expenses_by_category() -> List[Dict]:
    """Get expenses grouped by category"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT category, SUM(amount) as total, COUNT(*) as count
        FROM expenses
        GROUP BY category
        ORDER BY total DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_expenses_by_month() -> List[Dict]:
    """Get expenses grouped by month"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT strftime('%Y-%m', date) as month, SUM(amount) as total, COUNT(*) as count
        FROM expenses
        GROUP BY month
        ORDER BY month DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
