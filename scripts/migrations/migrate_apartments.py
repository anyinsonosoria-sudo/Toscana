"""
Migración para consolidar apartamentos y residentes
Agrega campos de residente directamente a la tabla apartments
"""
import sqlite3
from pathlib import Path

def migrate_apartments():
    # Conectar a la base de datos
    db_path = Path(__file__).parent / "data.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    print("=== Iniciando Migración de Apartamentos ===\n")
    
    # 1. Verificar si las columnas ya existen
    cur.execute("PRAGMA table_info(apartments)")
    columns = [col['name'] for col in cur.fetchall()]
    print(f"Columnas actuales en apartments: {columns}\n")
    
    # 2. Agregar nuevas columnas si no existen
    new_columns = [
        ("resident_name", "TEXT"),
        ("resident_role", "TEXT DEFAULT 'tenant'"),  # 'owner' o 'tenant'
        ("resident_email", "TEXT"),
        ("resident_phone", "TEXT"),
        ("payment_terms", "INTEGER DEFAULT 30")
    ]
    
    # Lista permitida de columnas válidas (whitelist)
    ALLOWED_COLUMNS = {
        "resident_name": "TEXT",
        "resident_role": "TEXT DEFAULT 'tenant'",
        "resident_email": "TEXT",
        "resident_phone": "TEXT",
        "payment_terms": "INTEGER DEFAULT 30"
    }
    
    for col_name, col_type in new_columns:
        if col_name not in columns:
            # Validar que la columna esté en la lista permitida
            if col_name not in ALLOWED_COLUMNS:
                print(f"⚠ Columna '{col_name}' no está en la lista permitida, omitiendo")
                continue
            
            try:
                # Usar el tipo de la whitelist para seguridad
                safe_col_type = ALLOWED_COLUMNS[col_name]
                # SQLite no permite parámetros en ALTER TABLE, pero validamos contra whitelist
                query = f"ALTER TABLE apartments ADD COLUMN {col_name} {safe_col_type}"
                cur.execute(query)
                print(f"✓ Columna '{col_name}' agregada")
            except Exception as e:
                print(f"⚠ Error agregando columna '{col_name}': {e}")
    
    conn.commit()
    
    # 3. Migrar datos de residentes a apartamentos
    print("\n=== Migrando Datos de Residentes ===\n")
    
    # Obtener todos los residentes
    cur.execute("""
        SELECT r.*, a.number as apt_number
        FROM residents r
        LEFT JOIN apartments a ON r.unit_id = a.id
        WHERE r.unit_id IS NOT NULL
        ORDER BY r.unit_id, r.role = 'owner' DESC
    """)
    residents = cur.fetchall()
    
    if not residents:
        print("No hay residentes para migrar\n")
    else:
        # Agrupar por unit_id y tomar el primero (preferiblemente owner)
        migrated = {}
        for resident in residents:
            unit_id = resident['unit_id']
            
            # Solo migrar el primer residente de cada apartamento (preferir owner)
            if unit_id not in migrated:
                try:
                    cur.execute("""
                        UPDATE apartments 
                        SET resident_name = ?,
                            resident_role = ?,
                            resident_email = ?,
                            resident_phone = ?,
                            payment_terms = ?
                        WHERE id = ?
                    """, (
                        resident['name'],
                        resident['role'] or 'tenant',
                        resident['email'],
                        resident['phone'],
                        resident['payment_terms'] or 30,
                        unit_id
                    ))
                    
                    role_text = "Propietario" if resident['role'] == 'owner' else "Inquilino"
                    print(f"✓ Apartamento {resident['apt_number']}: {resident['name']} ({role_text})")
                    migrated[unit_id] = True
                    
                except Exception as e:
                    print(f"✗ Error migrando apartamento {unit_id}: {e}")
    
    conn.commit()
    
    # 4. Mostrar resumen
    print("\n=== Resumen de Migración ===\n")
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(resident_name) as con_residente,
            COUNT(*) - COUNT(resident_name) as sin_residente
        FROM apartments
    """)
    stats = cur.fetchone()
    
    print(f"Total de apartamentos: {stats['total']}")
    print(f"Con residente asignado: {stats['con_residente']}")
    print(f"Sin residente: {stats['sin_residente']}")
    
    # Mostrar algunos ejemplos
    print("\n=== Apartamentos Actualizados ===\n")
    cur.execute("""
        SELECT number, resident_name, resident_role, resident_email, resident_phone
        FROM apartments
        WHERE resident_name IS NOT NULL
        LIMIT 5
    """)
    
    for apt in cur.fetchall():
        role_icon = "👑" if apt['resident_role'] == 'owner' else "🏠"
        print(f"{role_icon} Apt {apt['number']}: {apt['resident_name']}")
        if apt['resident_email']:
            print(f"   📧 {apt['resident_email']}")
        if apt['resident_phone']:
            print(f"   📱 {apt['resident_phone']}")
        print()
    
    conn.close()
    print("=== Migración Completada ===")

if __name__ == "__main__":
    migrate_apartments()
