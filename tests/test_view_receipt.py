#!/usr/bin/env python3
"""
Test script para verificar la funcionalidad de ver recibos
"""
import sqlite3
from pathlib import Path

# Conectar a la base de datos
db_path = Path(__file__).parent / "data.db"
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Obtener los gastos con recibos
cur.execute("SELECT id, description, receipt_path FROM expenses WHERE receipt_path IS NOT NULL ORDER BY id DESC LIMIT 5")
expenses = cur.fetchall()

print("=== GASTOS CON RECIBOS ===\n")

if not expenses:
    print("❌ No hay gastos con recibos registrados")
else:
    for exp in expenses:
        exp_id = exp['id']
        desc = exp['description']
        receipt_path = exp['receipt_path']
        
        # Verificar si el archivo existe
        file_path = Path(__file__).parent / receipt_path
        exists = "✓" if file_path.exists() else "✗"
        
        print(f"ID: {exp_id}")
        print(f"  Descripción: {desc}")
        print(f"  Ruta: {receipt_path}")
        print(f"  Archivo: {exists} {file_path}")
        if file_path.exists():
            file_size = file_path.stat().st_size
            print(f"  Tamaño: {file_size:,} bytes")
        print()

conn.close()

print("\n✓ Test completado")
