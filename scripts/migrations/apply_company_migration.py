"""
Aplicar migración de company_info
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"
MIGRATION_FILE = Path(__file__).parent / "migrations" / "003_create_company_info_table.sql"

def apply_migration():
    print("📦 Aplicando migración: company_info table")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        with open(MIGRATION_FILE, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        conn.executescript(sql_script)
        conn.commit()
        
        # Verificar que la tabla existe
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='company_info'
        """)
        
        if cursor.fetchone():
            print("✅ Tabla 'company_info' creada exitosamente")
            return True
        else:
            print("❌ Error: La tabla no se creó")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    apply_migration()
