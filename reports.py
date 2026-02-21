"""
Módulo de Reportes
Análisis y reportes de ventas, cuentas por cobrar y estadísticas financieras
"""

from typing import List, Dict, Optional
from db import get_conn
from datetime import datetime, timedelta
from pathlib import Path

LOG_PATH = Path(__file__).parent / "run.log"

def _log(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()}Z - {msg}\n")
    except Exception:
        pass

def get_sales_by_period(period: str = "month") -> List[Dict]:
    """Ventas agrupadas por período con montos reales cobrados"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        period_format = {
            'day': '%Y-%m-%d',
            'week': '%Y-W%W',
            'month': '%Y-%m',
            'year': '%Y'
        }
        fmt = period_format.get(period, '%Y-%m')
        
        cur.execute(f"""
            SELECT 
                strftime('{fmt}', i.issued_date) as period,
                COUNT(*) as total_invoices,
                SUM(i.amount) as total_amount,
                AVG(i.amount) as avg_amount,
                COALESCE(SUM(CASE WHEN i.paid = 1 THEN i.amount ELSE 0 END), 0) as paid_amount,
                COALESCE((
                    SELECT SUM(p.amount) FROM payments p
                    JOIN invoices i2 ON p.invoice_id = i2.id
                    WHERE strftime('{fmt}', i2.issued_date) = strftime('{fmt}', i.issued_date)
                ), 0) as collected
            FROM invoices i
            GROUP BY period
            ORDER BY period DESC
        """)
        
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        _log(f"Error in get_sales_by_period: {e}")
        return []

def get_sales_by_client(limit: int = 20) -> List[Dict]:
    """Ventas por cliente con montos reales pagados (JOIN con apartments)"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                i.unit_id as id,
                a.number as unit_number,
                COALESCE(a.resident_name, 'Unidad ' || a.number) as client_name,
                COUNT(i.id) as invoice_count,
                SUM(i.amount) as total_spent,
                COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id IN 
                    (SELECT id FROM invoices WHERE unit_id = i.unit_id)), 0) as paid_amount,
                SUM(i.amount) - COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id IN 
                    (SELECT id FROM invoices WHERE unit_id = i.unit_id)), 0) as pending_amount
            FROM invoices i
            LEFT JOIN apartments a ON i.unit_id = a.id
            GROUP BY i.unit_id
            ORDER BY total_spent DESC
            LIMIT ?
        """, (limit,))
        
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        _log(f"Error in get_sales_by_client: {e}")
        return []

def get_sales_by_service(limit: int = 15) -> List[Dict]:
    """Ventas por tipo de servicio desde descripciones de facturas"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                UPPER(TRIM(description)) as service_name,
                COUNT(*) as times_sold,
                SUM(amount) as total_revenue,
                AVG(amount) as avg_price
            FROM invoices
            WHERE description IS NOT NULL AND description != ''
            GROUP BY UPPER(TRIM(description))
            ORDER BY total_revenue DESC
            LIMIT ?
        """, (limit,))
        
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows] if rows else []
    except Exception as e:
        _log(f"Error in get_sales_by_service: {e}")
        return []

def get_accounts_receivable(status: Optional[str] = None, days_overdue: Optional[int] = None) -> List[Dict]:
    """
    Cuentas por cobrar con balance real (descontando pagos parciales).
    Solo muestra facturas que aún tienen saldo pendiente.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        query = """
            SELECT 
                i.id,
                i.id as invoice_number,
                i.issued_date,
                i.due_date,
                i.unit_id,
                a.number as unit_number,
                COALESCE(a.resident_name, 'Unidad ' || COALESCE(a.number, i.unit_id)) as client_name,
                i.amount as total,
                COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as paid_amount,
                i.amount - COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as balance,
                i.description,
                CAST((julianday('now') - julianday(i.issued_date)) AS INTEGER) as days_pending
            FROM invoices i
            LEFT JOIN apartments a ON i.unit_id = a.id
            WHERE i.paid = 0
              AND i.amount - COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) > 0
        """
        params = []
        
        if days_overdue:
            query += " AND julianday('now') - julianday(i.issued_date) > ?"
            params.append(days_overdue)
        
        query += " ORDER BY i.issued_date ASC"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        _log(f"Error in get_accounts_receivable: {e}")
        return []

def get_overdue_accounts(days: int = 30) -> List[Dict]:
    """Cuentas vencidas por más de X días con balance real"""
    return get_accounts_receivable(days_overdue=days)

def get_financial_summary(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict:
    """Resumen financiero general con montos reales de pagos"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Total facturado
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_invoiced, COUNT(*) as invoice_count
            FROM invoices
            WHERE DATE(issued_date) BETWEEN ? AND ?
        """, (date_from, date_to))
        sales = dict(cur.fetchone())
        
        # Total realmente cobrado (suma de payments, no solo flag paid)
        cur.execute("""
            SELECT COALESCE(SUM(p.amount), 0) as total_collected
            FROM payments p
            JOIN invoices i ON p.invoice_id = i.id
            WHERE DATE(i.issued_date) BETWEEN ? AND ?
        """, (date_from, date_to))
        collected = dict(cur.fetchone())
        
        # Pendiente real (facturado - cobrado)
        total_invoiced = sales.get('total_invoiced', 0) or 0
        total_collected = collected.get('total_collected', 0) or 0
        total_pending = total_invoiced - total_collected
        
        # Facturas pendientes count
        cur.execute("""
            SELECT COUNT(*) as pending_count
            FROM invoices
            WHERE paid = 0 AND DATE(issued_date) BETWEEN ? AND ?
        """, (date_from, date_to))
        pending_info = dict(cur.fetchone())
        
        # Gastos totales
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_expenses
            FROM expenses
            WHERE DATE(created_at) BETWEEN ? AND ?
        """, (date_from, date_to))
        expenses = dict(cur.fetchone())
        total_expenses = expenses.get('total_expenses', 0) or 0
        
        # Clientes activos
        cur.execute("""
            SELECT COUNT(DISTINCT unit_id) as active_clients
            FROM invoices
            WHERE DATE(issued_date) BETWEEN ? AND ?
        """, (date_from, date_to))
        clients = dict(cur.fetchone())
        
        conn.close()
        
        return {
            'total_invoiced': total_invoiced,
            'invoice_count': sales.get('invoice_count', 0),
            'total_collected': total_collected,
            'total_pending': total_pending,
            'pending_count': pending_info.get('pending_count', 0),
            'total_expenses': total_expenses,
            'net_income': total_collected - total_expenses,
            'active_clients': clients.get('active_clients', 0),
            'date_from': date_from,
            'date_to': date_to,
            'collection_rate': round((total_collected / total_invoiced * 100) if total_invoiced > 0 else 0, 1)
        }
    except Exception as e:
        _log(f"Error in get_financial_summary: {e}")
        return {}

def get_client_statement(unit_id: int) -> Dict:
    """Estado de cuenta detallado de un cliente"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Info del cliente desde apartments
        cur.execute("SELECT id, number, resident_name FROM apartments WHERE id = ?", (unit_id,))
        apt_row = cur.fetchone()
        if apt_row:
            apt = dict(apt_row)
            client = {'id': unit_id, 'unit_number': apt['number'], 'owner': apt['resident_name'] or f"Apto {apt['number']}"}
        else:
            client = {'id': unit_id, 'unit_number': '?', 'owner': f'Unidad {unit_id}'}
        
        # Facturas con pagos reales
        cur.execute("""
            SELECT 
                i.id, i.issued_date, i.amount as total, i.description,
                COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as paid_amount,
                i.amount - COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as balance,
                CASE WHEN i.paid = 1 THEN 'paid' ELSE 'pending' END as status
            FROM invoices i
            WHERE i.unit_id = ?
            ORDER BY i.issued_date DESC
        """, (unit_id,))
        
        invoices = [dict(r) for r in cur.fetchall()]
        conn.close()
        
        total_paid = sum(inv['paid_amount'] for inv in invoices)
        total_pending = sum(inv['balance'] for inv in invoices if inv['balance'] > 0)
        
        return {
            'client': client,
            'invoices': invoices,
            'total_paid': total_paid,
            'total_pending': total_pending
        }
    except Exception as e:
        _log(f"Error in get_client_statement: {e}")
        return {}

def get_top_clients(metric: str = 'sales', limit: int = 10) -> List[Dict]:
    """Clientes principales por métrica"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        if metric == 'invoices':
            select = 'COUNT(i.id) as metric_value'
        elif metric == 'pending':
            select = """SUM(i.amount) - COALESCE((SELECT SUM(p.amount) FROM payments p 
                        WHERE p.invoice_id IN (SELECT id FROM invoices WHERE unit_id = i.unit_id)), 0) as metric_value"""
        else:  # sales
            select = 'SUM(i.amount) as metric_value'
        
        cur.execute(f"""
            SELECT 
                i.unit_id as id,
                a.number as unit_number,
                COALESCE(a.resident_name, 'Unidad ' || COALESCE(a.number, i.unit_id)) as owner,
                {select}
            FROM invoices i
            LEFT JOIN apartments a ON i.unit_id = a.id
            GROUP BY i.unit_id
            ORDER BY metric_value DESC
            LIMIT ?
        """, (limit,))
        
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        _log(f"Error in get_top_clients: {e}")
        return []

def get_revenue_by_status() -> Dict[str, float]:
    """Ingresos por estado"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Cobrado real (suma de payments)
        cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments")
        paid = cur.fetchone()[0] or 0
        
        # Facturado total
        cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM invoices")
        invoiced = cur.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'Pagado': paid,
            'Pendiente': max(invoiced - paid, 0)
        }
    except Exception as e:
        _log(f"Error in get_revenue_by_status: {e}")
        return {}
