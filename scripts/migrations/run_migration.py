"""Ejecutar migración de permisos"""
import sqlite3

conn = sqlite3.connect('data.db')

with open('migrations/002_permissions_system.sql', 'r', encoding='utf-8') as f:
    conn.executescript(f.read())

conn.commit()
print('✅ Migración de permisos completada')

# Verificar
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) as count FROM permissions")
count = cursor.fetchone()[0]
print(f'   Total permisos creados: {count}')

conn.close()
