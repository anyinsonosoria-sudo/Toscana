import os
import sqlite3
from datetime import datetime

from app import create_app
import models
import apartments
import db as legacy_db

def main():
    app = create_app()
    with app.app_context():
        conn = legacy_db.get_conn()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        print("Buscando facturas recurrentes generadas el 2026-06-25...")
        
        # Buscar facturas autogeneradas (recurring_sale_id) de esa fecha
        cur.execute("""
            SELECT * FROM invoices 
            WHERE (issued_date = '2026-06-25' OR created_at LIKE '2026-06-25%')
              AND recurring_sale_id IS NOT NULL
        """)
        
        invoices = [dict(row) for row in cur.fetchall()]
        
        print(f"Se encontraron {len(invoices)} facturas.")
        
        for inv in invoices:
            try:
                sale_id = inv['recurring_sale_id']
                
                # Fetch sale
                cur.execute("SELECT * FROM recurring_sales WHERE id = ?", (sale_id,))
                sale_row = cur.fetchone()
                if not sale_row:
                    print(f" [SKIP] Venta recurrente {sale_id} no encontrada para la factura #{inv['id']}")
                    continue
                sale = dict(sale_row)
                
                # Fetch apartment
                apt = apartments.get_apartment(inv['unit_id'])
                
                email = apt.get('resident_email')
                
                print(f"Reenviando factura #{inv['id']} al Apt. {apt.get('number')} ({email or 'Sin email'})... ", end="")
                
                # Llamar a la función de notificación nativa
                models._notify_recurring_invoice(
                    invoice_id=inv['id'],
                    sale=sale,
                    apartment=apt,
                    service_name=inv['description'],
                    issued_date=inv.get('issued_date', '2026-06-25'),
                    due_date=inv.get('due_date', '2026-06-25')
                )
                print("OK")
                
            except Exception as e:
                print(f"ERROR: {e}")

if __name__ == '__main__':
    main()
