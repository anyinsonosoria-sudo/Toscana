"""Check current invoice state and sequence"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db import get_db

with get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt, MIN(id) as min_id, MAX(id) as max_id FROM invoices")
    r = cur.fetchone()
    print(f"Invoices: count={r[0]}, min_id={r[1]}, max_id={r[2]}")
    cur.execute("SELECT id, description, amount, issued_date, paid FROM invoices ORDER BY id")
    for row in cur.fetchall():
        print(f"  #{row[0]}: {row[1]} | ${row[2]} | {row[3]} | paid={row[4]}")
    # Check sqlite_sequence
    cur.execute("SELECT * FROM sqlite_sequence WHERE name='invoices'")
    seq = cur.fetchone()
    print(f"sqlite_sequence: {dict(seq) if seq else 'not found'}")
    # Check payments
    cur.execute("SELECT COUNT(*) FROM payments")
    print(f"Payments: {cur.fetchone()[0]}")
    # Check accounting_transactions income
    cur.execute("SELECT id, type, description, amount FROM accounting_transactions WHERE type='income'")
    for row in cur.fetchall():
        print(f"  accounting #{row[0]}: {row[1]} | {row[2]} | ${row[3]}")
