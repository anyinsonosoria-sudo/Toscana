"""
Reset completo: borra facturas, pagos, transacciones de pago.
Mantiene el saldo inicial de RD$ 15,000 (SALDO-INICIAL).
Reinicia la secuencia de facturas a 0 para que la próxima sea #1.
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

    # 4. Borrar transacciones contables de pago (INV-*), mantener saldo inicial
    cur.execute("SELECT COUNT(*) FROM accounting_transactions WHERE reference LIKE 'INV-%'")
    txn_count = cur.fetchone()[0]
    cur.execute("DELETE FROM accounting_transactions WHERE reference LIKE 'INV-%'")
    print(f"Eliminadas {txn_count} transacciones de pago (INV-*)")

    # 5. Reiniciar secuencia de facturas a 0
    cur.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'invoices'")
    if cur.rowcount == 0:
        cur.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('invoices', 0)")
    print("Secuencia de facturas reiniciada a 0 (próxima factura será #1)")

    # 6. Reiniciar secuencia de pagos también
    cur.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'payments'")
    if cur.rowcount == 0:
        cur.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('payments', 0)")
    print("Secuencia de pagos reiniciada a 0")

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
