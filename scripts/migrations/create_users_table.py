import sqlite3
from pathlib import Path

DB_PATH = Path("data.db")
SQL_FILE = Path("migrations/001_create_users_table.sql")

print("Creando tabla users...")
conn = sqlite3.connect(DB_PATH)

with open(SQL_FILE, 'r', encoding='utf-8') as f:
    sql_script = f.read()
    conn.executescript(sql_script)
    conn.commit()

print("✅ Tabla users creada exitosamente")

cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM users')
count = cur.fetchone()[0]
print(f'Usuarios en sistema: {count}')

if count > 0:
    cur.execute('SELECT username, role FROM users')
    for user in cur.fetchall():
        print(f'  - {user[0]} ({user[1]})')

conn.close()
print("\n🔐 Usuario por defecto:")
print("   Usuario: admin")
print("   Contraseña: admin123")
print("\n⚠️  CAMBIAR CONTRASEÑA EN PRIMER LOGIN!")
