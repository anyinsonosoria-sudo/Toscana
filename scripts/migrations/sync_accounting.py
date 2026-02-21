"""
Script de migración para sincronizar pagos y gastos existentes con la tabla de contabilidad
Este script debe ejecutarse una sola vez para migrar datos históricos
"""
from db import get_conn
from datetime import datetime

def sync_existing_payments():
    """Sincroniza todos los pagos existentes con accounting_transactions"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Obtener todos los pagos que no tienen transacción de contabilidad asociada
    cur.execute("""
        SELECT p.id, p.invoice_id, p.amount, p.paid_date, i.description
        FROM payments p
        LEFT JOIN invoices i ON p.invoice_id = i.id
        WHERE NOT EXISTS (
            SELECT 1 FROM accounting_transactions 
            WHERE reference = 'INV-' || p.invoice_id 
            AND type = 'income'
            AND amount = p.amount
            AND date = DATE(p.paid_date)
        )
    """)
    
    payments = cur.fetchall()
    synced_count = 0
    
    for payment in payments:
        payment_id = payment['id']
        invoice_id = payment['invoice_id']
        amount = payment['amount']
        paid_date = payment['paid_date']
        description = payment['description'] or f'Factura #{invoice_id}'
        
        # Convertir fecha si es necesario
        try:
            payment_date = datetime.fromisoformat(paid_date.replace('Z', '+00:00')).strftime('%Y-%m-%d')
        except:
            payment_date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            cur.execute("""
                INSERT INTO accounting_transactions(type, description, amount, category, reference, date)
                VALUES(?, ?, ?, ?, ?, ?)
            """, ('income', f'Pago recibido: {description}', amount, 'Ventas/Facturas', f'INV-{invoice_id}', payment_date))
            synced_count += 1
            print(f"✓ Sincronizado pago #{payment_id} - Factura #{invoice_id}: RD${amount}")
        except Exception as e:
            print(f"✗ Error sincronizando pago #{payment_id}: {e}")
    
    conn.commit()
    conn.close()
    return synced_count

def sync_existing_expenses():
    """Sincroniza todos los gastos existentes con accounting_transactions"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Obtener todos los gastos que no tienen transacción de contabilidad asociada
    cur.execute("""
        SELECT e.id, e.description, e.amount, e.category, e.date
        FROM expenses e
        WHERE NOT EXISTS (
            SELECT 1 FROM accounting_transactions 
            WHERE reference = 'EXP-' || e.id 
            AND type = 'expense'
        )
    """)
    
    expenses = cur.fetchall()
    synced_count = 0
    
    for expense in expenses:
        expense_id = expense['id']
        description = expense['description']
        amount = expense['amount']
        category = expense['category'] or 'General'
        date = expense['date']
        
        try:
            cur.execute("""
                INSERT INTO accounting_transactions(type, description, amount, category, reference, date)
                VALUES(?, ?, ?, ?, ?, ?)
            """, ('expense', f'Gasto: {description}', amount, category, f'EXP-{expense_id}', date))
            synced_count += 1
            print(f"✓ Sincronizado gasto #{expense_id} - {description}: RD${amount}")
        except Exception as e:
            print(f"✗ Error sincronizando gasto #{expense_id}: {e}")
    
    conn.commit()
    conn.close()
    return synced_count

def check_accounting_transactions():
    """Verifica cuántas transacciones hay en contabilidad"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) as total FROM accounting_transactions")
    total = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(*) as income_count FROM accounting_transactions WHERE type='income'")
    income_count = cur.fetchone()['income_count']
    
    cur.execute("SELECT COUNT(*) as expense_count FROM accounting_transactions WHERE type='expense'")
    expense_count = cur.fetchone()['expense_count']
    
    cur.execute("SELECT COUNT(*) as payments_count FROM payments")
    payments_count = cur.fetchone()['payments_count']
    
    cur.execute("SELECT COUNT(*) as expenses_count FROM expenses")
    expenses_count = cur.fetchone()['expenses_count']
    
    conn.close()
    
    return {
        'total_transactions': total,
        'income_transactions': income_count,
        'expense_transactions': expense_count,
        'total_payments': payments_count,
        'total_expenses': expenses_count
    }

if __name__ == "__main__":
    print("=" * 60)
    print("SINCRONIZACIÓN DE DATOS DE CONTABILIDAD")
    print("=" * 60)
    print()
    
    # Verificar estado actual
    print("Estado actual de la base de datos:")
    stats = check_accounting_transactions()
    print(f"  - Transacciones de contabilidad: {stats['total_transactions']}")
    print(f"    • Ingresos: {stats['income_transactions']}")
    print(f"    • Gastos: {stats['expense_transactions']}")
    print(f"  - Pagos registrados: {stats['total_payments']}")
    print(f"  - Gastos registrados: {stats['total_expenses']}")
    print()
    
    # Calcular cuántos necesitan sincronización
    missing_income = stats['total_payments'] - stats['income_transactions']
    missing_expenses = stats['total_expenses'] - stats['expense_transactions']
    
    if missing_income <= 0 and missing_expenses <= 0:
        print("✓ Todos los datos ya están sincronizados correctamente.")
        print()
    else:
        print(f"⚠ Faltan por sincronizar:")
        if missing_income > 0:
            print(f"  - {missing_income} pagos (ingresos)")
        if missing_expenses > 0:
            print(f"  - {missing_expenses} gastos")
        print()
        
        print("Iniciando sincronización...")
        print()
        
        # Sincronizar pagos
        if missing_income > 0:
            print("Sincronizando pagos...")
            synced_payments = sync_existing_payments()
            print(f"✓ {synced_payments} pagos sincronizados")
            print()
        
        # Sincronizar gastos
        if missing_expenses > 0:
            print("Sincronizando gastos...")
            synced_expenses = sync_existing_expenses()
            print(f"✓ {synced_expenses} gastos sincronizados")
            print()
        
        # Verificar nuevo estado
        print("Estado después de la sincronización:")
        stats = check_accounting_transactions()
        print(f"  - Transacciones de contabilidad: {stats['total_transactions']}")
        print(f"    • Ingresos: {stats['income_transactions']}")
        print(f"    • Gastos: {stats['expense_transactions']}")
        print()
    
    print("=" * 60)
    print("SINCRONIZACIÓN COMPLETADA")
    print("=" * 60)
    print()
    print("Ahora puedes:")
    print("  1. Revisar el módulo de Contabilidad")
    print("  2. Verificar el gráfico de Ingresos vs Gastos en el Dashboard")
    print()
