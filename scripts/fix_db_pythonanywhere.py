"""
Script de reparación completa de la base de datos para PythonAnywhere.
Ejecutar desde: cd ~/Toscana && python3 scripts/fix_db_pythonanywhere.py
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "data.db"

def add_column_if_missing(cur, table, column, definition):
    """Agrega una columna si no existe.
    
    SQLite ALTER TABLE no acepta DEFAULT CURRENT_TIMESTAMP (valor no constante).
    Se reemplaza automáticamente por DEFAULT NULL para evitar el error.
    """
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    if column not in cols:
        # Normalizar defaults no constantes que SQLite rechaza en ALTER TABLE
        safe_def = definition.replace("DEFAULT CURRENT_TIMESTAMP", "DEFAULT NULL")
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {safe_def}")
        print(f"  ✓ {table}.{column} agregada")
    else:
        print(f"  - {table}.{column} ya existe")

def create_table_if_missing(cur, name, ddl):
    """Crea una tabla si no existe."""
    cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    if not cur.fetchone():
        cur.execute(ddl)
        print(f"  ✓ Tabla {name} creada")
    else:
        print(f"  - Tabla {name} ya existe")

def main():
    print(f"\n=== Reparación de BD: {DB_PATH} ===\n")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ── products_services ──────────────────────────────────────────────────────
    print("[products_services]")
    add_column_if_missing(cur, "products_services", "additional_notes", "TEXT")

    # ── recurring_sales ────────────────────────────────────────────────────────
    print("\n[recurring_sales]")
    create_table_if_missing(cur, "recurring_sales", """
        CREATE TABLE recurring_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER NOT NULL,
            service_id INTEGER,
            amount REAL NOT NULL,
            frequency TEXT NOT NULL DEFAULT 'monthly',
            billing_day INTEGER DEFAULT 1,
            billing_time TEXT DEFAULT '08:00',
            start_date TEXT NOT NULL,
            end_date TEXT,
            description TEXT,
            active INTEGER DEFAULT 1,
            last_generated TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (unit_id) REFERENCES apartments(id) ON DELETE CASCADE
        )
    """)
    add_column_if_missing(cur, "recurring_sales", "billing_time", "TEXT DEFAULT '08:00'")
    add_column_if_missing(cur, "recurring_sales", "service_id", "INTEGER")
    add_column_if_missing(cur, "recurring_sales", "description", "TEXT")
    add_column_if_missing(cur, "recurring_sales", "last_generated", "TEXT")

    # ── invoices ───────────────────────────────────────────────────────────────
    print("\n[invoices]")
    add_column_if_missing(cur, "invoices", "status", "TEXT DEFAULT 'pending'")
    add_column_if_missing(cur, "invoices", "notes", "TEXT")
    add_column_if_missing(cur, "invoices", "invoice_number", "TEXT")
    add_column_if_missing(cur, "invoices", "service_id", "INTEGER")
    add_column_if_missing(cur, "invoices", "pdf_path", "TEXT")
    add_column_if_missing(cur, "invoices", "created_at", "TEXT DEFAULT CURRENT_TIMESTAMP")
    add_column_if_missing(cur, "invoices", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP")
    add_column_if_missing(cur, "invoices", "tax_rate", "REAL DEFAULT 0")
    add_column_if_missing(cur, "invoices", "tax_amount", "REAL DEFAULT 0")
    add_column_if_missing(cur, "invoices", "subtotal", "REAL DEFAULT 0")
    add_column_if_missing(cur, "invoices", "recurring_sale_id", "INTEGER")
    add_column_if_missing(cur, "invoices", "pending_amount", "REAL DEFAULT 0")

    # ── payments ───────────────────────────────────────────────────────────────
    print("\n[payments]")
    add_column_if_missing(cur, "payments", "notes", "TEXT")
    add_column_if_missing(cur, "payments", "reference", "TEXT")
    add_column_if_missing(cur, "payments", "receipt_path", "TEXT")
    add_column_if_missing(cur, "payments", "created_at", "TEXT DEFAULT CURRENT_TIMESTAMP")

    # ── apartments ─────────────────────────────────────────────────────────────
    print("\n[apartments]")
    add_column_if_missing(cur, "apartments", "additional_notes", "TEXT")
    add_column_if_missing(cur, "apartments", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP")

    # ── expenses ───────────────────────────────────────────────────────────────
    print("\n[expenses]")
    add_column_if_missing(cur, "expenses", "status", "TEXT DEFAULT 'pending'")
    add_column_if_missing(cur, "expenses", "invoice_number", "TEXT")
    add_column_if_missing(cur, "expenses", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP")

    # ── suppliers ──────────────────────────────────────────────────────────────
    print("\n[suppliers]")
    add_column_if_missing(cur, "suppliers", "notes", "TEXT")
    add_column_if_missing(cur, "suppliers", "tax_id", "TEXT")
    add_column_if_missing(cur, "suppliers", "supplier_type", "TEXT DEFAULT 'general'")
    add_column_if_missing(cur, "suppliers", "supplier_type_other", "TEXT")
    add_column_if_missing(cur, "suppliers", "contact_name", "TEXT")
    add_column_if_missing(cur, "suppliers", "payment_terms", "INTEGER DEFAULT 30")
    add_column_if_missing(cur, "suppliers", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP")

    # ── accounting_transactions ────────────────────────────────────────────────
    print("\n[accounting_transactions]")
    create_table_if_missing(cur, "accounting_transactions", """
        CREATE TABLE accounting_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT CHECK(type IN ('income', 'expense', 'transfer')),
            description TEXT,
            amount REAL NOT NULL,
            category TEXT,
            reference TEXT,
            date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    add_column_if_missing(cur, "accounting_transactions", "account_from", "TEXT")
    add_column_if_missing(cur, "accounting_transactions", "account_to", "TEXT")
    add_column_if_missing(cur, "accounting_transactions", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP")

    # ── company_info ───────────────────────────────────────────────────────────
    print("\n[company_info]")
    create_table_if_missing(cur, "company_info", """
        CREATE TABLE company_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            address TEXT,
            phone TEXT,
            email TEXT,
            tax_id TEXT,
            logo_path TEXT,
            currency TEXT DEFAULT 'DOP',
            website TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── customization_settings ─────────────────────────────────────────────────
    print("\n[customization_settings]")
    create_table_if_missing(cur, "customization_settings", """
        CREATE TABLE customization_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── residents ──────────────────────────────────────────────────────────────
    print("\n[residents]")
    create_table_if_missing(cur, "residents", """
        CREATE TABLE residents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER,
            name TEXT,
            email TEXT,
            phone TEXT,
            role TEXT DEFAULT 'tenant',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    add_column_if_missing(cur, "residents", "role_other", "TEXT")
    add_column_if_missing(cur, "residents", "payment_terms", "INTEGER DEFAULT 30")

    # ── Índices útiles ─────────────────────────────────────────────────────────
    print("\n[índices]")
    indexes = [
        ("idx_recurring_active", "CREATE INDEX IF NOT EXISTS idx_recurring_active ON recurring_sales(active)"),
        ("idx_recurring_unit",   "CREATE INDEX IF NOT EXISTS idx_recurring_unit ON recurring_sales(unit_id)"),
        ("idx_invoices_status",  "CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status)"),
        ("idx_payments_invoice", "CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id)"),
        ("idx_residents_unit",   "CREATE INDEX IF NOT EXISTS idx_residents_unit ON residents(unit_id)"),
    ]
    for name, ddl in indexes:
        cur.execute(ddl)
        print(f"  ✓ Índice {name}")

    # ── Actualizar pending_amount en facturas existentes ───────────────────────
    print("\n[pending_amount - sincronización]")
    cur.execute("""
        UPDATE invoices
        SET pending_amount = MAX(
            amount - COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = invoices.id), 0),
            0
        )
        WHERE paid = 0
    """)
    rows = cur.rowcount
    print(f"  ✓ {rows} facturas pendientes actualizadas con saldo correcto")

    conn.commit()
    conn.close()
    print("\n✅ Base de datos reparada correctamente.\n")

if __name__ == "__main__":
    main()
