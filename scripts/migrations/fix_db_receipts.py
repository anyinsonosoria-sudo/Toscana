#!/usr/bin/env python
"""
Verificar y arreglar estructura de base de datos para OCR
"""

import db
import sqlite3

conn = db.get_conn()
cur = conn.cursor()

print("=" * 70)
print("VERIFICACIÓN DE TABLA EXPENSES")
print("=" * 70)

# Verificar estructura actual
cur.execute("PRAGMA table_info(expenses)")
columns = cur.fetchall()

print("\nColumnas actuales:")
column_names = []
for col in columns:
    print(f"  {col[1]}: {col[2]}")
    column_names.append(col[1])

# Verificar si receipt_path existe
if 'receipt_path' not in column_names:
    print("\n❌ Columna 'receipt_path' NO EXISTE")
    print("\nAgregando columna receipt_path...")
    try:
        cur.execute("ALTER TABLE expenses ADD COLUMN receipt_path TEXT")
        conn.commit()
        print("✓ Columna receipt_path agregada correctamente")
    except Exception as e:
        print(f"✗ Error al agregar columna: {e}")
        conn.rollback()
else:
    print("\n✓ Columna 'receipt_path' ya existe")

conn.close()
print("\n" + "=" * 70)
