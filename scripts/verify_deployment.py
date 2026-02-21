"""
Script de verificación de despliegue PythonAnywhere.
Compara la versión desplegada contra el repositorio y valida 
que la BD tenga todas las columnas y tablas requeridas.

Ejecutar: cd ~/Toscana && python3 scripts/verify_deployment.py
"""
import sqlite3
import os
import subprocess
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "data.db"
BASE_DIR = Path(__file__).parent.parent

# ═══════════════════════════════════════════════════════════
# 1. Verificar sincronización con Git
# ═══════════════════════════════════════════════════════════
def check_git_sync():
    print("\n" + "="*60)
    print("1. SINCRONIZACIÓN GIT")
    print("="*60)
    
    try:
        # Verificar si hay cambios pendientes
        result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True, cwd=str(BASE_DIR))
        if result.stdout.strip():
            print("  ✗ Hay cambios locales no committeados:")
            for line in result.stdout.strip().split('\n'):
                print(f"    {line}")
        else:
            print("  ✓ Directorio limpio (sin cambios locales)")
        
        # Verificar si está actualizado con remote
        subprocess.run(['git', 'fetch', '--quiet'], capture_output=True, cwd=str(BASE_DIR))
        result = subprocess.run(['git', 'log', 'HEAD..origin/main', '--oneline'], 
                              capture_output=True, text=True, cwd=str(BASE_DIR))
        if result.stdout.strip():
            print("  ✗ Hay commits pendientes de descargar:")
            for line in result.stdout.strip().split('\n'):
                print(f"    {line}")
            print("  → Ejecuta: git pull")
        else:
            print("  ✓ Actualizado con origin/main")
        
        # Mostrar último commit
        result = subprocess.run(['git', 'log', '-1', '--format=%h %s (%ci)'], 
                              capture_output=True, text=True, cwd=str(BASE_DIR))
        print(f"  ℹ Último commit: {result.stdout.strip()}")
        
    except Exception as e:
        print(f"  ✗ Error verificando git: {e}")


# ═══════════════════════════════════════════════════════════
# 2. Verificar esquema de base de datos
# ═══════════════════════════════════════════════════════════
def check_db_schema():
    print("\n" + "="*60)
    print("2. ESQUEMA DE BASE DE DATOS")
    print("="*60)
    
    # Columnas requeridas por cada tabla
    REQUIRED_COLUMNS = {
        'invoices': [
            'id', 'unit_id', 'description', 'amount', 'issued_date', 'due_date', 
            'paid', 'pending_amount', 'recurring_sale_id', 'notes'
        ],
        'payments': [
            'id', 'invoice_id', 'amount', 'paid_date', 'method', 'notes'
        ],
        'suppliers': [
            'id', 'name', 'email', 'phone', 'address', 'supplier_type',
            'supplier_type_other', 'contact_name', 'tax_id', 'payment_terms'
        ],
        'apartments': [
            'id', 'number', 'resident_name', 'resident_email', 'resident_phone',
            'resident_role', 'payment_terms'
        ],
        'recurring_sales': [
            'id', 'unit_id', 'service_id', 'amount', 'frequency', 'billing_day',
            'billing_time', 'start_date', 'description', 'active', 'last_generated'
        ],
        'company_info': [
            'id', 'name', 'legal_id', 'address', 'city', 'country', 'phone',
            'email', 'tax_id', 'logo_path', 'website', 'bank_name',
            'bank_account', 'bank_routing', 'notes'
        ],
        'products_services': [
            'id', 'code', 'name', 'type', 'description', 'price', 'active',
            'additional_notes'
        ],
        'users': ['id', 'username', 'email', 'password_hash', 'role', 'is_active'],
        'residents': ['id', 'unit_id', 'name', 'email', 'phone', 'role'],
        'accounting_transactions': ['id', 'type', 'description', 'amount', 'category', 'reference', 'date'],
        'customization_settings': ['id', 'key', 'value'],
    }

    REQUIRED_TABLES = list(REQUIRED_COLUMNS.keys())
    
    if not DB_PATH.exists():
        print(f"  ✗ Base de datos no encontrada: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Tablas existentes
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    existing_tables = {row[0] for row in cur.fetchall()}
    
    errors = 0
    warnings = 0
    
    for table in REQUIRED_TABLES:
        if table not in existing_tables:
            print(f"  ✗ Tabla FALTANTE: {table}")
            errors += 1
            continue
        
        cur.execute(f"PRAGMA table_info({table})")
        existing_cols = {row[1] for row in cur.fetchall()}
        
        missing = [c for c in REQUIRED_COLUMNS[table] if c not in existing_cols]
        if missing:
            print(f"  ✗ {table}: columnas faltantes → {', '.join(missing)}")
            errors += 1
        else:
            print(f"  ✓ {table}: OK ({len(REQUIRED_COLUMNS[table])} columnas verificadas)")
    
    conn.close()
    
    if errors:
        print(f"\n  ⚠ {errors} problemas encontrados. Ejecuta: python3 scripts/fix_db_pythonanywhere.py")
    else:
        print(f"\n  ✓ Todas las tablas y columnas están correctas")


# ═══════════════════════════════════════════════════════════
# 3. Verificar variables de entorno (WSGI)
# ═══════════════════════════════════════════════════════════
def check_env_vars():
    print("\n" + "="*60)
    print("3. VARIABLES DE ENTORNO")
    print("="*60)
    
    required = {
        'SECRET_KEY': True,
        'FLASK_ENV': True,
    }
    
    smtp_vars = {
        'SMTP_HOST': False,
        'SMTP_PORT': False,
        'SMTP_USER': False,
        'SMTP_PASSWORD': False,
        'SMTP_FROM': False,
    }
    
    for var, is_required in required.items():
        val = os.environ.get(var, '')
        if val:
            display = val[:8] + '...' if len(val) > 8 else val
            print(f"  ✓ {var} = {display}")
        else:
            print(f"  ✗ {var} — NO CONFIGURADA {'(REQUERIDA)' if is_required else ''}")
    
    print("\n  [SMTP - Notificaciones por email]")
    smtp_ok = True
    for var in smtp_vars:
        val = os.environ.get(var, '')
        if val:
            display = val[:8] + '...' if len(val) > 8 else val
            if 'PASSWORD' in var:
                display = '********'
            print(f"  ✓ {var} = {display}")
        else:
            smtp_ok = False
            print(f"  ✗ {var} — no configurada")
    
    if not smtp_ok:
        print("\n  ⚠ Las notificaciones por email NO funcionarán sin configurar SMTP")
        print("    Agrega las variables en el archivo WSGI de PythonAnywhere:")
        print("    /var/www/toscana_pythonanywhere_com_wsgi.py")
        print("    Ejemplo:")
        print("      os.environ['SMTP_HOST'] = 'smtp.gmail.com'")
        print("      os.environ['SMTP_PORT'] = '587'")
        print("      os.environ['SMTP_USER'] = 'tu@gmail.com'")
        print("      os.environ['SMTP_PASSWORD'] = 'tu-app-password'")
        print("      os.environ['SMTP_FROM'] = 'tu@gmail.com'")
    else:
        print("  ✓ SMTP configurado correctamente")


# ═══════════════════════════════════════════════════════════
# 4. Verificar archivos clave
# ═══════════════════════════════════════════════════════════
def check_key_files():
    print("\n" + "="*60)
    print("4. ARCHIVOS CLAVE")
    print("="*60)
    
    files_to_check = [
        'app.py',
        'db.py',
        'models.py',
        'senders.py',
        'billing.py',
        'blueprints/billing.py',
        'blueprints/apartments.py',
        'blueprints/suppliers.py',
        'blueprints/products.py',
        'blueprints/expenses.py',
        'templates/base.html',
        'templates/index.html',
        'templates/facturacion.html',
        'templates/registrar_pago.html',
        'templates/apartamentos.html',
    ]
    
    for f in files_to_check:
        fp = BASE_DIR / f
        if fp.exists():
            size = fp.stat().st_size
            print(f"  ✓ {f} ({size:,} bytes)")
        else:
            print(f"  ✗ {f} — NO ENCONTRADO")


# ═══════════════════════════════════════════════════════════
# 5. Verificar datos críticos
# ═══════════════════════════════════════════════════════════
def check_data():
    print("\n" + "="*60)
    print("5. DATOS DE LA APLICACIÓN")
    print("="*60)
    
    if not DB_PATH.exists():
        print("  ✗ BD no encontrada")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    counts = [
        ('users', 'SELECT COUNT(*) FROM users'),
        ('apartments', 'SELECT COUNT(*) FROM apartments'),
        ('invoices (total)', 'SELECT COUNT(*) FROM invoices'),
        ('invoices (pendientes)', 'SELECT COUNT(*) FROM invoices WHERE paid = 0'),
        ('invoices (con recurring_sale_id)', 'SELECT COUNT(*) FROM invoices WHERE recurring_sale_id IS NOT NULL'),
        ('payments', 'SELECT COUNT(*) FROM payments'),
        ('recurring_sales', 'SELECT COUNT(*) FROM recurring_sales'),
        ('products_services', 'SELECT COUNT(*) FROM products_services'),
        ('suppliers', 'SELECT COUNT(*) FROM suppliers'),
        ('residents', 'SELECT COUNT(*) FROM residents'),
        ('company_info', 'SELECT COUNT(*) FROM company_info'),
    ]
    
    for label, query in counts:
        try:
            cur.execute(query)
            count = cur.fetchone()[0]
            print(f"  {label}: {count}")
        except Exception as e:
            print(f"  ✗ {label}: Error — {e}")
    
    # Verificar facturas duplicadas (mismo unit_id, descripción y fecha)
    print("\n  [Posibles facturas duplicadas]")
    try:
        cur.execute("""
            SELECT unit_id, description, issued_date, COUNT(*) as cnt
            FROM invoices
            GROUP BY unit_id, description, issued_date
            HAVING cnt > 1
        """)
        dupes = cur.fetchall()
        if dupes:
            for d in dupes:
                print(f"  ⚠ Apto #{d['unit_id']} — '{d['description']}' — {d['issued_date']} (×{d['cnt']})")
            print(f"  → Total: {len(dupes)} grupo(s) de duplicados encontrados")
        else:
            print("  ✓ No se encontraron facturas duplicadas")
    except Exception as e:
        print(f"  ✗ Error verificando duplicados: {e}")
    
    # Facturas con pending_amount sin actualizar
    print("\n  [Verificar pending_amount]")
    try:
        cur.execute("""
            SELECT i.id, i.amount, i.pending_amount,
                   COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as real_paid
            FROM invoices i
            WHERE i.paid = 0
        """)
        wrong = []
        for row in cur.fetchall():
            real_pending = max(row['amount'] - row['real_paid'], 0)
            if row['pending_amount'] is None or abs(row['pending_amount'] - real_pending) > 0.01:
                wrong.append(row['id'])
        
        if wrong:
            print(f"  ⚠ {len(wrong)} facturas con pending_amount desactualizado: {wrong[:10]}")
            print(f"  → Ejecuta: python3 scripts/fix_db_pythonanywhere.py (corrige esto automáticamente)")
        else:
            print("  ✓ pending_amount correctos en todas las facturas pendientes")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    conn.close()


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  VERIFICACIÓN DE DESPLIEGUE — Toscana/Xpack             ║")
    print("╚══════════════════════════════════════════════════════════╝")
    
    check_git_sync()
    check_db_schema()
    check_env_vars()
    check_key_files()
    check_data()
    
    print("\n" + "="*60)
    print("VERIFICACIÓN COMPLETADA")
    print("="*60 + "\n")
