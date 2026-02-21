"""
Setup Database - Ejecuta migraciones y configuración inicial
Crea la tabla de usuarios y usuario admin por defecto
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

def run_migration(conn, migration_file):
    """Ejecuta un archivo de migración SQL"""
    print(f"  ➤ Ejecutando: {migration_file.name}")
    
    try:
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Ejecutar script completo
        conn.executescript(sql_script)
        conn.commit()
        
        print(f"    ✅ Migración exitosa")
        return True
        
    except Exception as e:
        print(f"    ❌ Error: {e}")
        conn.rollback()
        return False

def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║  CONFIGURACIÓN DE BASE DE DATOS                          ║
    ║  Building Maintenance System v2.0                        ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Conectar a base de datos
    print(f"\n📁 Base de datos: {DB_PATH}")
    
    if DB_PATH.exists():
        print("⚠️  La base de datos ya existe")
        response = input("¿Desea ejecutar las migraciones de todas formas? (s/n): ")
        if response.lower() != 's':
            print("❌ Operación cancelada")
            return False
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        # Habilitar foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        
        print("\n📦 Ejecutando migraciones...\n")
        
        # Ejecutar migraciones en orden
        if MIGRATIONS_DIR.exists():
            migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
            
            if not migration_files:
                print("⚠️  No se encontraron archivos de migración")
            
            for migration_file in migration_files:
                run_migration(conn, migration_file)
        else:
            print(f"⚠️  Directorio de migraciones no existe: {MIGRATIONS_DIR}")
            print("   Creando tabla de usuarios manualmente...")
            
            # Crear tabla manualmente si no hay directorio de migraciones
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT,
                    role TEXT NOT NULL DEFAULT 'operator' CHECK(role IN ('admin', 'operator', 'resident')),
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME
                );
                
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
                
                INSERT OR IGNORE INTO users (username, email, password_hash, full_name, role, is_active)
                VALUES (
                    'admin',
                    'admin@building.local',
                    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5NU7667qpO3oa',
                    'Administrador del Sistema',
                    'admin',
                    1
                );
            """)
            conn.commit()
            print("    ✅ Tabla de usuarios creada")
        
        # Verificar que la tabla existe
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='users'
        """)
        
        if cursor.fetchone():
            # Contar usuarios
            cursor.execute("SELECT COUNT(*) as count FROM users")
            user_count = cursor.fetchone()[0]
            
            print(f"\n✅ BASE DE DATOS CONFIGURADA CORRECTAMENTE")
            print(f"\n📊 Resumen:")
            print(f"   • Tabla 'users' creada: ✅")
            print(f"   • Usuarios registrados: {user_count}")
            
            if user_count > 0:
                # Mostrar usuarios
                cursor.execute("""
                    SELECT username, email, role, is_active 
                    FROM users 
                    ORDER BY id
                """)
                
                print(f"\n👥 Usuarios en el sistema:")
                for user in cursor.fetchall():
                    status = "✅ Activo" if user[3] else "❌ Inactivo"
                    print(f"   • {user[0]} ({user[2]}) - {user[1]} - {status}")
            
            print(f"\n🔐 Credenciales por defecto:")
            print(f"   Usuario: admin")
            print(f"   Contraseña: admin123")
            print(f"\n⚠️  IMPORTANTE: Cambiar la contraseña en el primer login!")
            
            return True
        else:
            print("\n❌ Error: La tabla 'users' no se creó correctamente")
            return False
            
    except Exception as e:
        print(f"\n❌ Error durante la configuración: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    success = main()
    
    if success:
        print("\n" + "="*60)
        print("🚀 La base de datos está lista!")
        print("   Puedes iniciar la aplicación con: python app.py")
        print("="*60 + "\n")
    
    sys.exit(0 if success else 1)
