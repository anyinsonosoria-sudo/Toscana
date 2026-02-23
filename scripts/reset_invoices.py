"""
Reset completo: borra facturas, pagos, transacciones de pago y ventas recurrentes.
Mantiene el saldo inicial de RD$ 15,000 (SALDO-INICIAL).
Reinicia todas las secuencias a 0.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db import get_db

with get_db() as conn:
    cur = conn.cursor()

    # 1. Borrar pagos
    cur.execute("SELECT COUNT(*) FROM payments")
    pay_count = cur.fetchone()[0]
    cur.execute("DELETE FROM payments")
    print(f"Eliminados {pay_count} pagos")

    # 2. Borrar líneas de factura (invoice_lines)
    try:
        cur.execute("SELECT COUNT(*) FROM invoice_lines")
        lines_count = cur.fetchone()[0]
        cur.execute("DELETE FROM invoice_lines")
        print(f"Eliminadas {lines_count} líneas de factura")
    except Exception:
        print("Tabla invoice_lines no existe, saltando")

    # 3. Borrar facturas
    cur.execute("SELECT COUNT(*) FROM invoices")
    inv_count = cur.fetchone()[0]
    cur.execute("DELETE FROM invoices")
    print(f"Eliminadas {inv_count} facturas")

    # 4. Borrar ventas recurrentes
    try:
        cur.execute("SELECT COUNT(*) FROM recurring_sales")
        rec_count = cur.fetchone()[0]
        cur.execute("DELETE FROM recurring_sales")
        print(f"Eliminadas {rec_count} ventas recurrentes")
    except Exception:
        print("Tabla recurring_sales no existe, saltando")

    # 5. Borrar transacciones contables de pago (INV-*), mantener saldo inicial
    cur.execute("SELECT COUNT(*) FROM accounting_transactions WHERE reference LIKE 'INV-%'")
    txn_count = cur.fetchone()[0]
    cur.execute("DELETE FROM accounting_transactions WHERE reference LIKE 'INV-%'")
    print(f"Eliminadas {txn_count} transacciones de pago (INV-*)")

    # 6. Reiniciar secuencias
    for table in ['invoices', 'payments', 'recurring_sales']:
        cur.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = ?", (table,))
        if cur.rowcount == 0:
            try:
                cur.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, 0)", (table,))
            except Exception:
                pass
        print(f"Secuencia {table} reiniciada a 0")

    conn.commit()

    # Verificar
    print("\n--- Verificación ---")
    cur.execute("SELECT COUNT(*) FROM invoices")
    print(f"Facturas: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM payments")
    print(f"Pagos: {cur.fetchone()[0]}")
    cur.execute("SELECT * FROM accounting_transactions")
    rows = cur.fetchall()
    print(f"Transacciones contables restantes: {len(rows)}")
    for r in rows:
        print(f"  #{r['id']}: {r['type']} | {r['description']} | ${r['amount']}")
    cur.execute("SELECT * FROM sqlite_sequence WHERE name IN ('invoices', 'payments')")
    for r in cur.fetchall():
        print(f"  Secuencia {r['name']}: {r['seq']}")
