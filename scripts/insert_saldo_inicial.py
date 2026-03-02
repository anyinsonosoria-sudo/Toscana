"""Insertar saldo inicial de RD$ 15,000 en accounting_transactions"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db import get_db

with get_db() as conn:
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO accounting_transactions (type, description, amount, category, reference, date, notes)
           VALUES ('income', 'Efectivo en cuenta Banreservas al 22-02-2026', 15000.00, 'Saldo Inicial', 'SALDO-INICIAL', '2026-02-22', 'Balance inicial en cuenta Banreservas')"""
    )
    conn.commit()
    print(f"Insertado con ID: {cur.lastrowid}")
    cur.execute("SELECT * FROM accounting_transactions WHERE id=?", (cur.lastrowid,))
    row = cur.fetchone()
    for k in row.keys():
        print(f"  {k}: {row[k]}")
