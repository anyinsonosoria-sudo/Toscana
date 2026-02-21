"""
Módulo de base de datos para Building Maintenance.
Maneja conexiones SQLite y migraciones.
"""
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

# Configuración de ruta
_default_db = Path(__file__).parent / 'data' / 'data.db'
DB_PATH = Path(os.environ.get('BUILDING_MAINTENANCE_DB', str(_default_db)))

_initialized = False


@contextmanager
def get_db():
    """Context manager para conexiones seguras a la BD."""
    conn = None
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def get_conn():
    """Obtiene conexión directa (legacy, preferir get_db())."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def test_connection() -> bool:
    """Verifica la conexión a la base de datos."""
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def ensure_initialized():
    """Inicializa la BD solo si no se ha hecho."""
    global _initialized
    if not _initialized:
        init_db()
        _initialized = True


def init_db():
    """Inicializa el esquema de la base de datos."""
    global _initialized
    
    with get_db() as conn:
        cur = conn.cursor()
        
        # Crear tablas principales
        _create_schema(cur)
        
        # Crear usuario admin si corresponde
        _create_default_admin(cur)
        
        conn.commit()
    
    # Aplicar migraciones
    _apply_migrations()
    
    _initialized = True


def _create_schema(cur):
    """Crea todas las tablas del esquema."""
    # Users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        role TEXT NOT NULL DEFAULT 'operator' 
            CHECK(role IN ('admin', 'operator', 'resident')),
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_login DATETIME
    )
    """)
    
    # Apartments
    cur.execute("""
    CREATE TABLE IF NOT EXISTS apartments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT UNIQUE NOT NULL,
        floor TEXT,
        notes TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        resident_name TEXT,
        resident_role TEXT DEFAULT 'tenant',
        resident_email TEXT,
        resident_phone TEXT,
        payment_terms INTEGER DEFAULT 30
    )
    """)
    
    # Invoices
    cur.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        unit_id INTEGER,
        description TEXT,
        amount REAL,
        issued_date TEXT DEFAULT CURRENT_TIMESTAMP,
        due_date TEXT,
        paid INTEGER DEFAULT 0,
        pending_amount REAL DEFAULT 0,
        recurring_sale_id INTEGER,
        notes TEXT,
        FOREIGN KEY(unit_id) REFERENCES apartments(id) ON DELETE SET NULL
    )
    """)
    
    # Payments
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER,
        amount REAL,
        paid_date TEXT DEFAULT CURRENT_TIMESTAMP,
        method TEXT,
        notes TEXT,
        FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
    )
    """)
    
    # Expenses
    cur.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT,
        amount REAL,
        category TEXT,
        supplier_id INTEGER,
        date TEXT,
        payment_method TEXT,
        notes TEXT,
        receipt_path TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
    )
    """)
    
    # Suppliers
    cur.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact TEXT,
        contact_name TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        supplier_type TEXT DEFAULT 'general',
        supplier_type_other TEXT,
        tax_id TEXT,
        payment_terms INTEGER DEFAULT 30,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Products/Services
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products_services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        name TEXT NOT NULL,
        type TEXT CHECK(type IN ('product', 'service')),
        description TEXT,
        price REAL NOT NULL DEFAULT 0,
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Accounting transactions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS accounting_transactions (
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
    
    # Índices
    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_apartments_number ON apartments(number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_unit ON invoices(unit_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_due ON invoices(due_date)")


def _create_default_admin(cur):
    """Crea usuario admin por defecto si está permitido."""
    if os.environ.get('AUTO_CREATE_ADMIN', '1') != '1':
        return
    
    if os.environ.get('FLASK_ENV') == 'production':
        # En produccion, requerir configuracion explicita
        if not os.environ.get('ADMIN_PASSWORD'):
            print("[WARN] ADMIN_PASSWORD no configurado, omitiendo creacion de admin")
            return
    
    try:
        import bcrypt
        
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@building.local')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        
        admin_hash = bcrypt.hashpw(
            admin_password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')
        
        cur.execute("""
            INSERT OR IGNORE INTO users 
            (username, email, password_hash, full_name, role, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            admin_username,
            admin_email,
            admin_hash,
            'Administrador del Sistema',
            'admin',
            1
        ))
        
    except ImportError:
        print("[WARN] bcrypt no disponible, omitiendo creacion de admin")


def _apply_migrations():
    """Aplica migraciones SQL pendientes."""
    migrations_dir = Path(__file__).parent / 'migrations'
    if not migrations_dir.exists():
        return
    
    with get_db() as conn:
        cur = conn.cursor()
        
        # Tabla de tracking
        cur.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            id INTEGER PRIMARY KEY,
            filename TEXT UNIQUE NOT NULL,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Migraciones ya aplicadas
        cur.execute("SELECT filename FROM _migrations")
        applied = {row[0] for row in cur.fetchall()}
        
        # Aplicar pendientes
        for sql_file in sorted(migrations_dir.glob('*.sql')):
            if sql_file.name in applied:
                continue
            
            try:
                sql_text = sql_file.read_text(encoding='utf-8')
                # Ejecutar cada sentencia por separado para tolerar columnas ya existentes
                statements = [s.strip() for s in sql_text.split(';') if s.strip() and not s.strip().startswith('--')]
                for stmt in statements:
                    try:
                        conn.execute(stmt)
                    except Exception as stmt_err:
                        msg = str(stmt_err).lower()
                        # Ignorar errores de columna/índice ya existente
                        if 'already has a column' in msg or 'already exists' in msg:
                            print(f"[MIGRATION] SKIP (ya existe): {stmt[:60]}...")
                        else:
                            raise stmt_err
                cur.execute(
                    "INSERT INTO _migrations (filename) VALUES (?)",
                    (sql_file.name,)
                )
                conn.commit()
                print(f"[MIGRATION] OK {sql_file.name}")
            except Exception as e:
                conn.rollback()
                print(f"[MIGRATION] ERROR {sql_file.name}: {e}")


def reset_db():
    """Elimina y recrea la base de datos."""
    global _initialized
    
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"[OK] Base de datos eliminada: {DB_PATH}")
    
    _initialized = False
    init_db()
    print("[OK] Esquema recreado")