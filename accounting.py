from typing import List, Dict, Optional
from db import get_conn
from datetime import datetime

def add_transaction(transaction_type: str, description: str, amount: float,
                   category: Optional[str] = None, reference: Optional[str] = None,
                   date: Optional[str] = None, notes: Optional[str] = None) -> int:
    """Add a new accounting transaction (income or expense)"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""INSERT INTO accounting_transactions(type, description, amount, category, reference, date, notes) 
                   VALUES(?,?,?,?,?,?,?)""",
                (transaction_type, description, amount, category, reference, date, notes))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid

def list_transactions(transaction_type: Optional[str] = None) -> List[Dict]:
    """List all transactions, optionally filtered by type"""
    conn = get_conn()
    cur = conn.cursor()
    if transaction_type:
        cur.execute("""
            SELECT id, type, description, amount, category, reference, date, notes, created_at
            FROM accounting_transactions
            WHERE type = ?
            ORDER BY date DESC, created_at DESC
        """, (transaction_type,))
    else:
        cur.execute("""
            SELECT id, type, description, amount, category, reference, date, notes, created_at
            FROM accounting_transactions
            ORDER BY date DESC, created_at DESC
        """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_transaction(transaction_id: int) -> Optional[Dict]:
    """Get a single transaction by ID"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounting_transactions WHERE id=?", (transaction_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_transaction(transaction_id: int, **fields) -> None:
    """Update a transaction with given fields"""
    if not fields:
        return
    
    # Whitelist de columnas permitidas
    ALLOWED_COLUMNS = {'type', 'description', 'amount', 'category', 'reference', 'date', 'notes'}
    
    keys = []
    vals = []
    for k, v in fields.items():
        if k not in ALLOWED_COLUMNS:
            raise ValueError(f"Columna '{k}' no permitida para actualización")
        keys.append(f"{k}=?")
        vals.append(v)
    vals.append(transaction_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE accounting_transactions SET {', '.join(keys)} WHERE id=?", vals)
    conn.commit()
    conn.close()

def delete_transaction(transaction_id: int) -> None:
    """Delete a transaction"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM accounting_transactions WHERE id=?", (transaction_id,))
    conn.commit()
    conn.close()

def get_balance_summary() -> Dict:
    """Get summary of income, expenses, and balance"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Get total income
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM accounting_transactions WHERE type='income'")
    total_income = cur.fetchone()[0]
    
    # Get total expenses
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM accounting_transactions WHERE type='expense'")
    total_expenses = cur.fetchone()[0]
    
    conn.close()
    
    return {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'balance': total_income - total_expenses
    }

def get_transactions_by_category(transaction_type: Optional[str] = None) -> List[Dict]:
    """Get transactions grouped by category"""
    conn = get_conn()
    cur = conn.cursor()
    if transaction_type:
        cur.execute("""
            SELECT category, type, SUM(amount) as total, COUNT(*) as count
            FROM accounting_transactions
            WHERE type = ?
            GROUP BY category, type
            ORDER BY total DESC
        """, (transaction_type,))
    else:
        cur.execute("""
            SELECT category, type, SUM(amount) as total, COUNT(*) as count
            FROM accounting_transactions
            GROUP BY category, type
            ORDER BY total DESC
        """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_transactions_by_month(transaction_type: Optional[str] = None) -> List[Dict]:
    """Get transactions grouped by month"""
    conn = get_conn()
    cur = conn.cursor()
    if transaction_type:
        cur.execute("""
            SELECT strftime('%Y-%m', date) as month, type, SUM(amount) as total, COUNT(*) as count
            FROM accounting_transactions
            WHERE type = ?
            GROUP BY month, type
            ORDER BY month DESC
        """, (transaction_type,))
    else:
        cur.execute("""
            SELECT strftime('%Y-%m', date) as month, type, SUM(amount) as total, COUNT(*) as count
            FROM accounting_transactions
            GROUP BY month, type
            ORDER BY month DESC
        """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════
#  ESTADO DE RESULTADOS (Income Statement / P&L)
# ═══════════════════════════════════════════════════════════════

def get_income_statement(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict:
    """
    Generate a full Income Statement (Estado de Resultados).
    Combines:
      - Operating income: payments received on invoices  
      - Other income: accounting_transactions type='income'
      - Operating expenses: from expenses table
      - Other expenses: accounting_transactions type='expense'
    """
    from datetime import datetime, timedelta

    if not date_to:
        date_to = datetime.now().strftime('%Y-%m-%d')
    if not date_from:
        # Default: first day of the current month
        date_from = datetime.now().strftime('%Y-%m-01')

    conn = get_conn()
    cur = conn.cursor()

    # ── INGRESOS OPERACIONALES (pagos recibidos en facturas) ──
    cur.execute("""
        SELECT COALESCE(SUM(p.amount), 0)
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        WHERE DATE(p.paid_date) BETWEEN ? AND ?
    """, (date_from, date_to))
    operating_income = cur.fetchone()[0] or 0

    # Desglose de ingresos operacionales por categoría (descripción de factura)
    cur.execute("""
        SELECT COALESCE(UPPER(TRIM(i.description)), 'SIN CATEGORÍA') as category,
               SUM(p.amount) as total
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        WHERE DATE(p.paid_date) BETWEEN ? AND ?
        GROUP BY category
        ORDER BY total DESC
    """, (date_from, date_to))
    operating_income_detail = [dict(r) for r in cur.fetchall()]

    # ── OTROS INGRESOS (transacciones contables tipo income, excluyendo pagos de facturas) ──
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM accounting_transactions
        WHERE type = 'income' AND DATE(date) BETWEEN ? AND ?
          AND (reference IS NULL OR reference NOT LIKE 'INV-%')
    """, (date_from, date_to))
    other_income = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COALESCE(category, 'Sin Categoría') as category, SUM(amount) as total
        FROM accounting_transactions
        WHERE type = 'income' AND DATE(date) BETWEEN ? AND ?
          AND (reference IS NULL OR reference NOT LIKE 'INV-%')
        GROUP BY category
        ORDER BY total DESC
    """, (date_from, date_to))
    other_income_detail = [dict(r) for r in cur.fetchall()]

    # ── GASTOS OPERACIONALES (tabla expenses) ──
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE DATE(COALESCE(date, created_at)) BETWEEN ? AND ?
    """, (date_from, date_to))
    operating_expenses = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COALESCE(category, 'Sin Categoría') as category, SUM(amount) as total
        FROM expenses
        WHERE DATE(COALESCE(date, created_at)) BETWEEN ? AND ?
        GROUP BY category
        ORDER BY total DESC
    """, (date_from, date_to))
    operating_expenses_detail = [dict(r) for r in cur.fetchall()]

    # ── OTROS GASTOS (transacciones contables tipo expense, excluyendo gastos operacionales) ──
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM accounting_transactions
        WHERE type = 'expense' AND DATE(date) BETWEEN ? AND ?
          AND (reference IS NULL OR reference NOT LIKE 'EXP-%')
    """, (date_from, date_to))
    other_expenses = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COALESCE(category, 'Sin Categoría') as category, SUM(amount) as total
        FROM accounting_transactions
        WHERE type = 'expense' AND DATE(date) BETWEEN ? AND ?
          AND (reference IS NULL OR reference NOT LIKE 'EXP-%')
        GROUP BY category
        ORDER BY total DESC
    """, (date_from, date_to))
    other_expenses_detail = [dict(r) for r in cur.fetchall()]

    conn.close()

    total_income = operating_income + other_income
    total_expenses = operating_expenses + other_expenses
    gross_profit = operating_income - operating_expenses
    net_income = total_income - total_expenses

    return {
        'date_from': date_from,
        'date_to': date_to,
        'operating_income': operating_income,
        'operating_income_detail': operating_income_detail,
        'other_income': other_income,
        'other_income_detail': other_income_detail,
        'total_income': total_income,
        'operating_expenses': operating_expenses,
        'operating_expenses_detail': operating_expenses_detail,
        'other_expenses': other_expenses,
        'other_expenses_detail': other_expenses_detail,
        'total_expenses': total_expenses,
        'gross_profit': gross_profit,
        'net_income': net_income,
    }


# ═══════════════════════════════════════════════════════════════
#  ESTADO DE FLUJO DE EFECTIVO (Cash Flow Statement)
# ═══════════════════════════════════════════════════════════════

def get_cash_flow_statement(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict:
    """
    Generate a Cash Flow Statement (Estado de Flujo de Efectivo).
    Sections:
      1. Operating Activities  - invoice collections + operating expenses
      2. Investing Activities  - (placeholder, no fixed-asset data yet)
      3. Financing Activities  - accounting txn income/expense labeled as 'financing'
    """
    from datetime import datetime, timedelta

    if not date_to:
        date_to = datetime.now().strftime('%Y-%m-%d')
    if not date_from:
        date_from = datetime.now().strftime('%Y-%m-01')

    conn = get_conn()
    cur = conn.cursor()

    # ── 1. ACTIVIDADES DE OPERACIÓN ──

    # Cobros a clientes (payments on invoices)
    cur.execute("""
        SELECT COALESCE(SUM(p.amount), 0)
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        WHERE DATE(p.paid_date) BETWEEN ? AND ?
    """, (date_from, date_to))
    collections = cur.fetchone()[0] or 0

    # Pagos a proveedores / gastos operacionales
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM expenses
        WHERE DATE(COALESCE(date, created_at)) BETWEEN ? AND ?
    """, (date_from, date_to))
    operational_payments = cur.fetchone()[0] or 0

    # Detalle de cobros por mes
    cur.execute("""
        SELECT strftime('%Y-%m', p.paid_date) as period, SUM(p.amount) as total
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        WHERE DATE(p.paid_date) BETWEEN ? AND ?
        GROUP BY period ORDER BY period
    """, (date_from, date_to))
    collections_by_month = [dict(r) for r in cur.fetchall()]

    # Detalle de gastos operacionales por mes
    cur.execute("""
        SELECT strftime('%Y-%m', COALESCE(date, created_at)) as period, SUM(amount) as total
        FROM expenses
        WHERE DATE(COALESCE(date, created_at)) BETWEEN ? AND ?
        GROUP BY period ORDER BY period
    """, (date_from, date_to))
    expenses_by_month = [dict(r) for r in cur.fetchall()]

    net_operating = collections - operational_payments

    # ── 2. ACTIVIDADES DE INVERSIÓN ──
    # (Placeholder — no fixed-asset or investment tables yet)
    investing_inflows = 0
    investing_outflows = 0
    net_investing = 0

    # ── 3. ACTIVIDADES DE FINANCIAMIENTO ──
    # Income transactions from accounting_transactions as financing inflows
    # Excluir los que ya se contaron como ingresos operacionales (pagos de facturas)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM accounting_transactions
        WHERE type = 'income' AND DATE(date) BETWEEN ? AND ?
          AND (reference IS NULL OR reference NOT LIKE 'INV-%')
    """, (date_from, date_to))
    financing_inflows = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COALESCE(category, 'Sin Categoría') as category, SUM(amount) as total
        FROM accounting_transactions
        WHERE type = 'income' AND DATE(date) BETWEEN ? AND ?
          AND (reference IS NULL OR reference NOT LIKE 'INV-%')
        GROUP BY category ORDER BY total DESC
    """, (date_from, date_to))
    financing_inflows_detail = [dict(r) for r in cur.fetchall()]

    # Expense transactions from accounting_transactions as financing outflows
    # Excluir los que ya se contaron como gastos operacionales
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM accounting_transactions
        WHERE type = 'expense' AND DATE(date) BETWEEN ? AND ?
          AND (reference IS NULL OR reference NOT LIKE 'EXP-%')
    """, (date_from, date_to))
    financing_outflows = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COALESCE(category, 'Sin Categoría') as category, SUM(amount) as total
        FROM accounting_transactions
        WHERE type = 'expense' AND DATE(date) BETWEEN ? AND ?
          AND (reference IS NULL OR reference NOT LIKE 'EXP-%')
        GROUP BY category ORDER BY total DESC
    """, (date_from, date_to))
    financing_outflows_detail = [dict(r) for r in cur.fetchall()]

    net_financing = financing_inflows - financing_outflows

    # ── SALDO INICIAL (todo antes del período) ──
    cur.execute("""
        SELECT COALESCE(SUM(p.amount), 0) FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        WHERE DATE(p.paid_date) < ?
    """, (date_from,))
    opening_collections = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE DATE(COALESCE(date, created_at)) < ?
    """, (date_from,))
    opening_expenses = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END), 0)
        FROM accounting_transactions WHERE DATE(date) < ?
          AND (
            (type = 'income' AND (reference IS NULL OR reference NOT LIKE 'INV-%'))
            OR
            (type = 'expense' AND (reference IS NULL OR reference NOT LIKE 'EXP-%'))
          )
    """, (date_from,))
    opening_acct = cur.fetchone()[0] or 0

    conn.close()

    opening_balance = opening_collections - opening_expenses + opening_acct
    net_change = net_operating + net_investing + net_financing
    closing_balance = opening_balance + net_change

    return {
        'date_from': date_from,
        'date_to': date_to,
        # Operating
        'collections': collections,
        'collections_by_month': collections_by_month,
        'operational_payments': operational_payments,
        'expenses_by_month': expenses_by_month,
        'net_operating': net_operating,
        # Investing
        'investing_inflows': investing_inflows,
        'investing_outflows': investing_outflows,
        'net_investing': net_investing,
        # Financing
        'financing_inflows': financing_inflows,
        'financing_inflows_detail': financing_inflows_detail,
        'financing_outflows': financing_outflows,
        'financing_outflows_detail': financing_outflows_detail,
        'net_financing': net_financing,
        # Totals
        'opening_balance': opening_balance,
        'net_change': net_change,
        'closing_balance': closing_balance,
    }
