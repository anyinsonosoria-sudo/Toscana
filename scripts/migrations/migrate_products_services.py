"""
Script para migrar la tabla products_services agregando el campo additional_notes
"""
import sqlite3
from pathlib import Path

def migrate_products_services():
    db_path = Path(__file__).parent / "building_maintenance.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Verificar si la tabla existe
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products_services'")
    table_exists = cur.fetchone()
    
    if not table_exists:
        print("La tabla products_services no existe. Ejecuta db.py para crear la base de datos primero.")
        conn.close()
        return
    
    # Verificar si la columna ya existe
    cur.execute("PRAGMA table_info(products_services)")
    columns = [col[1] for col in cur.fetchall()]
    
    if 'additional_notes' not in columns:
        print("Agregando columna 'additional_notes' a la tabla products_services...")
        
        # Agregar la nueva columna
        cur.execute("ALTER TABLE products_services ADD COLUMN additional_notes TEXT")
        
        # Migrar datos existentes: mover description a additional_notes
        cur.execute("UPDATE products_services SET additional_notes = description WHERE description IS NOT NULL")
        
        # Limpiar el campo description para que solo tenga el nombre
        cur.execute("UPDATE products_services SET description = name")
        
        conn.commit()
        print("✓ Migración completada exitosamente")
        print("✓ Campo 'additional_notes' agregado")
        print("✓ Datos migrados: description → additional_notes")
    else:
        print("La columna 'additional_notes' ya existe. No se requiere migración.")
    
    conn.close()

if __name__ == "__main__":
    migrate_products_services()
