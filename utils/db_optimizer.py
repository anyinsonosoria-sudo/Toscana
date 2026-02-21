"""
Database Optimization Helpers
==============================
Helpers para optimizar queries y performance de la base de datos.

SECURITY: Todas las operaciones SQL usan lista blanca de tablas
para prevenir SQL Injection.
"""

import sqlite3
import db
import re

# ==========================================
# SECURITY: Lista blanca de tablas permitidas
# ==========================================
ALLOWED_TABLES = frozenset([
    'apartments',
    'invoices', 
    'payments',
    'expenses',
    'suppliers',
    'users',
    'permissions',
    'user_permissions',
    'residents',
    'units',
    'charges',
    'services',
    'maintenance_records',
    'company_info',
    'accounting_transactions',
    'products_services',
    'customization_settings',
    'recurring_invoices'
])

# Patrón seguro para nombres de índices
SAFE_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _validate_table_name(table: str) -> bool:
    """
    Valida que el nombre de tabla esté en la lista blanca.
    SECURITY: Previene SQL Injection.
    
    Args:
        table: Nombre de la tabla a validar
        
    Returns:
        bool: True si es válida
        
    Raises:
        ValueError: Si la tabla no está permitida
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"[SECURITY] Tabla no permitida: {table}")
    return True


def _validate_identifier(name: str) -> bool:
    """
    Valida que un identificador SQL sea seguro.
    
    Args:
        name: Nombre del identificador (columna, índice, etc.)
        
    Returns:
        bool: True si es válido
        
    Raises:
        ValueError: Si el identificador no es válido
    """
    if not SAFE_IDENTIFIER_PATTERN.match(name):
        raise ValueError(f"[SECURITY] Identificador no válido: {name}")
    return True


def create_indexes():
    """
    Crea índices en la base de datos para mejorar performance.
    
    Índices recomendados:
    - apartments: number (búsquedas por número)
    - invoices: apartment_id, date, status (filtrado común)
    - payments: invoice_id, date (joins frecuentes)
    - expenses: date, category (reportes)
    - users: username, email (autenticación)
    """
    conn = db.get_conn()
    cur = conn.cursor()
    
    indexes = [
        # Apartamentos
        ("idx_apartments_number", "apartments", "number"),
        ("idx_apartments_floor", "apartments", "floor"),
        
        # Facturas
        ("idx_invoices_apartment", "invoices", "apartment_id"),
        ("idx_invoices_date", "invoices", "date"),
        ("idx_invoices_status", "invoices", "status"),
        ("idx_invoices_apt_date", "invoices", "apartment_id, date"),
        
        # Pagos
        ("idx_payments_invoice", "payments", "invoice_id"),
        ("idx_payments_date", "payments", "date"),
        
        # Gastos
        ("idx_expenses_date", "expenses", "date"),
        ("idx_expenses_category", "expenses", "category"),
        ("idx_expenses_supplier", "expenses", "supplier_id"),
        
        # Usuarios
        ("idx_users_username", "users", "username"),
        ("idx_users_email", "users", "email"),
        ("idx_users_role", "users", "role"),
        
        # Permisos
        ("idx_user_permissions_user", "user_permissions", "user_id"),
        ("idx_user_permissions_perm", "user_permissions", "permission_id"),
    ]
    
    created = 0
    skipped = 0
    
    for index_name, table_name, columns in indexes:
        try:
            # SECURITY: Validar nombres antes de usar en SQL
            _validate_table_name(table_name)
            _validate_identifier(index_name)
            # Validar cada columna en columns (pueden ser múltiples)
            for col in columns.replace(' ', '').split(','):
                _validate_identifier(col)
            
            # Verificar si el índice ya existe (usando parámetros)
            cur.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name=?
            """, (index_name,))
            
            if cur.fetchone():
                print(f"[SKIP] Indice {index_name} ya existe")
                skipped += 1
                continue
            
            # Crear índice (seguro porque validamos arriba)
            cur.execute(f"""
                CREATE INDEX {index_name} 
                ON {table_name}({columns})
            """)
            print(f"[OK] Indice creado: {index_name} en {table_name}({columns})")
            created += 1
            
        except ValueError as e:
            print(f"[SECURITY] {e}")
        except sqlite3.Error as e:
            print(f"[WARNING] Error creando {index_name}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n[INFO] Indices creados: {created}, Existentes: {skipped}")
    return created, skipped


def analyze_database():
    """
    Ejecuta ANALYZE para actualizar estadísticas del query planner.
    Mejora la selección de índices por SQLite.
    """
    conn = db.get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("ANALYZE")
        conn.commit()
        print("[OK] Database analyzed - Estadísticas actualizadas")
        return True
    except sqlite3.Error as e:
        print(f"[ERROR] Error analyzing database: {e}")
        return False
    finally:
        conn.close()


def vacuum_database():
    """
    Ejecuta VACUUM para desfragmentar y optimizar la base de datos.
    Libera espacio y reorganiza índices.
    
    NOTA: Puede tomar tiempo en bases de datos grandes.
    """
    conn = db.get_conn()
    
    try:
        # VACUUM requiere autocommit mode
        conn.execute("VACUUM")
        print("[OK] Database vacuumed - Espacio optimizado")
        return True
    except sqlite3.Error as e:
        print(f"[ERROR] Error vacuuming database: {e}")
        return False
    finally:
        conn.close()


def get_table_stats():
    """
    Obtiene estadísticas de las tablas principales.
    
    Returns:
        dict: Diccionario con conteos por tabla
    """
    conn = db.get_conn()
    cur = conn.cursor()
    
    stats = {}
    
    tables = [
        'apartments',
        'invoices',
        'payments',
        'expenses',
        'suppliers',
        'users',
        'permissions',
        'user_permissions'
    ]
    
    for table in tables:
        try:
            # SECURITY: Validar tabla contra lista blanca
            _validate_table_name(table)
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            stats[table] = count
        except ValueError as e:
            print(f"[SECURITY] {e}")
            stats[table] = 0
        except sqlite3.Error:
            stats[table] = 0
    
    conn.close()
    return stats


def get_index_stats():
    """
    Obtiene información sobre índices existentes.
    
    Returns:
        list: Lista de índices con sus tablas
    """
    conn = db.get_conn()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT name, tbl_name 
            FROM sqlite_master 
            WHERE type='index' 
            AND name NOT LIKE 'sqlite_%'
            ORDER BY tbl_name, name
        """)
        
        indexes = []
        for name, table in cur.fetchall():
            indexes.append({'name': name, 'table': table})
        
        return indexes
    finally:
        conn.close()


def explain_query(query, params=None):
    """
    Muestra el plan de ejecución de un query.
    Útil para debug de performance.
    
    SECURITY: Solo permite queries SELECT para prevenir ataques.
    
    Args:
        query: SQL query a analizar (solo SELECT permitido)
        params: Parámetros del query
    
    Returns:
        list: Plan de ejecución
        
    Raises:
        ValueError: Si el query no es un SELECT
    """
    # SECURITY: Solo permitir queries SELECT
    query_upper = query.strip().upper()
    if not query_upper.startswith('SELECT'):
        raise ValueError("[SECURITY] explain_query solo permite queries SELECT")
    
    # SECURITY: Prevenir múltiples statements
    if ';' in query:
        raise ValueError("[SECURITY] No se permiten múltiples statements")
    
    conn = db.get_conn()
    cur = conn.cursor()
    
    try:
        # Usar parámetros seguros
        explain_sql = f"EXPLAIN QUERY PLAN {query}"
        if params:
            cur.execute(explain_sql, params)
        else:
            cur.execute(explain_sql)
        
        plan = cur.fetchall()
        
        print("\n[QUERY PLAN]")
        for row in plan:
            print(f"  {row}")
        
        return plan
    except ValueError:
        raise
    except sqlite3.Error as e:
        print(f"[ERROR] Error explaining query: {e}")
        return []
    finally:
        conn.close()


def optimize_database():
    """
    Ejecuta todos los pasos de optimización.
    
    Pasos:
    1. Crea índices faltantes
    2. Actualiza estadísticas (ANALYZE)
    3. Opcionalmente desfragmenta (VACUUM)
    
    Returns:
        dict: Resultados de la optimización
    """
    print("=" * 60)
    print("OPTIMIZACION DE BASE DE DATOS")
    print("=" * 60)
    
    results = {}
    
    # Estadísticas antes
    print("\n[1] Estadísticas actuales:")
    stats_before = get_table_stats()
    for table, count in stats_before.items():
        print(f"  {table}: {count} registros")
    
    # Crear índices
    print("\n[2] Creando índices...")
    created, skipped = create_indexes()
    results['indexes_created'] = created
    results['indexes_skipped'] = skipped
    
    # Analizar
    print("\n[3] Analizando base de datos...")
    analyze_success = analyze_database()
    results['analyze_success'] = analyze_success
    
    # Índices actuales
    print("\n[4] Índices existentes:")
    indexes = get_index_stats()
    for idx in indexes:
        print(f"  {idx['name']} en {idx['table']}")
    results['total_indexes'] = len(indexes)
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Indices nuevos: {created}")
    print(f"Indices existentes: {skipped}")
    print(f"Total indices: {len(indexes)}")
    print(f"Tablas optimizadas: {len(stats_before)}")
    
    if analyze_success:
        print("\n[OK] Base de datos optimizada exitosamente")
    else:
        print("\n[WARNING] Optimización completada con advertencias")
    
    return results


if __name__ == "__main__":
    # Ejecutar optimización si se llama directamente
    optimize_database()
