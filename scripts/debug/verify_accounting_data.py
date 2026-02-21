"""
Script de verificación para asegurar que los datos están correctos
"""
from db import get_conn
import accounting
from datetime import datetime, timedelta
import calendar

def verify_data():
    print("=" * 60)
    print("VERIFICACIÓN DE DATOS")
    print("=" * 60)
    print()
    
    # 1. Verificar transacciones en la base de datos
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) as total FROM accounting_transactions")
    total = cur.fetchone()['total']
    print(f"Total de transacciones: {total}")
    
    cur.execute("SELECT type, COUNT(*) as count, SUM(amount) as total FROM accounting_transactions GROUP BY type")
    rows = cur.fetchall()
    for row in rows:
        print(f"  - {row['type']}: {row['count']} transacciones, Total: RD${row['total']:,.2f}")
    print()
    
    # 2. Verificar que accounting.list_transactions() funciona
    print("Probando accounting.list_transactions()...")
    try:
        transactions = accounting.list_transactions()
        print(f"✓ Se recuperaron {len(transactions)} transacciones")
        
        income = [t for t in transactions if t['type'] == 'income']
        expenses = [t for t in transactions if t['type'] == 'expense']
        
        print(f"  - Ingresos: {len(income)} transacciones")
        print(f"  - Gastos: {len(expenses)} transacciones")
        print()
        
        # Mostrar algunas transacciones de ejemplo
        if transactions:
            print("Primeras 5 transacciones:")
            for i, t in enumerate(transactions[:5], 1):
                print(f"  {i}. {t['type'].upper()} - {t['description']} - RD${t['amount']:,.2f} - {t['date']}")
            print()
    except Exception as e:
        print(f"✗ Error: {e}")
        print()
    
    # 3. Simular el cálculo del dashboard (últimos 6 meses)
    print("Simulando cálculo del dashboard (últimos 6 meses)...")
    months_labels = []
    income_data = []
    expense_data = []
    
    for i in range(5, -1, -1):
        date = datetime.now() - timedelta(days=30*i)
        month_name = calendar.month_name[date.month][:3]
        year = date.year
        label = f"{month_name} {year}"
        months_labels.append(label)
        
        # Calcular ingresos del mes
        month_start = date.replace(day=1).strftime('%Y-%m-%d')
        if date.month == 12:
            month_end = date.replace(year=date.year+1, month=1, day=1).strftime('%Y-%m-%d')
        else:
            month_end = date.replace(month=date.month+1, day=1).strftime('%Y-%m-%d')
        
        try:
            transactions = accounting.list_transactions()
            month_income = sum(t['amount'] for t in transactions 
                             if t['type'] == 'income' and month_start <= t['date'] < month_end)
            month_expense = sum(t['amount'] for t in transactions 
                              if t['type'] == 'expense' and month_start <= t['date'] < month_end)
            income_data.append(month_income)
            expense_data.append(month_expense)
            
            print(f"  {label}: Ingresos RD${month_income:,.2f}, Gastos RD${month_expense:,.2f}")
        except Exception as e:
            print(f"  {label}: Error - {e}")
            income_data.append(0)
            expense_data.append(0)
    
    print()
    print(f"Datos para el gráfico:")
    print(f"  Meses: {months_labels}")
    print(f"  Ingresos: {income_data}")
    print(f"  Gastos: {expense_data}")
    print()
    
    # 4. Verificar balance
    print("Balance de contabilidad:")
    try:
        balance = accounting.get_balance_summary()
        print(f"  - Total Ingresos: RD${balance['total_income']:,.2f}")
        print(f"  - Total Gastos: RD${balance['total_expenses']:,.2f}")
        print(f"  - Balance: RD${balance['balance']:,.2f}")
    except Exception as e:
        print(f"  Error: {e}")
    
    conn.close()
    
    print()
    print("=" * 60)
    print("VERIFICACIÓN COMPLETADA")
    print("=" * 60)

if __name__ == "__main__":
    verify_data()
