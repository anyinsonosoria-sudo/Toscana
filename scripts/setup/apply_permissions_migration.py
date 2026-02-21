"""
Script para aplicar la migración de permisos y asignar todos los permisos al usuario admin (id=1)
"""
import sqlite3
from pathlib import Path
import os

DB_PATH = Path(__file__).parent.parent.parent / "data.db"
MIGRATION_PATH = Path(__file__).parent.parent.parent / "migrations" / "002_permissions_system.sql"

print(f"[DEBUG] Usando base de datos: {DB_PATH.resolve()}")
print(f"[DEBUG] Usando migración: {MIGRATION_PATH.resolve()}")

# 1. Ejecutar la migración SQL para crear tablas y poblar permisos
def run_migration():
    with open(MIGRATION_PATH, encoding="utf-8") as f:
        sql = f.read()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(sql)
        print("[OK] Migración ejecutada correctamente.")
    finally:
        conn.close()

# 2. Asignar todos los permisos al usuario admin (id=1)
def grant_all_permissions_to_admin():
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM permissions")
        perm_ids = [row[0] for row in cur.fetchall()]
        for perm_id in perm_ids:
            try:
                cur.execute("INSERT OR IGNORE INTO user_permissions (user_id, permission_id, granted_by) VALUES (1, ?, 1)", (perm_id,))
            except Exception as e:
                print(f"[WARN] No se pudo asignar permiso {perm_id}: {e}")
        conn.commit()
        print(f"[OK] {len(perm_ids)} permisos asignados al admin (id=1)")
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
    grant_all_permissions_to_admin()
    print("[DONE] Permisos listos. Reinicia el servidor Flask.")
