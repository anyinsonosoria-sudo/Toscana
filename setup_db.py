import sqlite3
import os

db_path = os.path.join('data', 'data.db')
print(f"Conectando a la base de datos: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Crear la tabla de reported_payments manualmente
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reported_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER,
        resident_id INTEGER,
        amount FLOAT,
        reference VARCHAR(120),
        date_reported VARCHAR(50) DEFAULT CURRENT_TIMESTAMP,
        status VARCHAR(20) DEFAULT 'pending',
        FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
        FOREIGN KEY(resident_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')
    
    conn.commit()
    print("¡Éxito! La tabla 'reported_payments' se ha creado correctamente.")
except Exception as e:
    print(f"Ocurrió un error: {e}")
finally:
    if 'conn' in locals():
        conn.close()
