"""Script para verificar usuarios en la base de datos"""
import sqlite3

conn = sqlite3.connect('data.db')
cursor = conn.cursor()

cursor.execute('SELECT id, username, password_hash FROM users')
rows = cursor.fetchall()

print("\n=== Usuarios en la base de datos ===")
for row in rows:
    hash_preview = row[2][:30] if row[2] else "VACÍO/NULL"
    print(f"ID: {row[0]}, Usuario: {row[1]}, Hash: {hash_preview}...")

conn.close()
