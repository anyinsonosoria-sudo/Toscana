# -*- coding: utf-8 -*-
"""Script para verificar tablas en la base de datos"""
import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

try:
    conn = sqlite3.connect('data.db')
    cur = conn.cursor()
    
    # Listar todas las tablas
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    
    print("\n" + "="*50)
    print("TABLAS EN LA BASE DE DATOS")
    print("="*50)
    for table in tables:
        print(f"  - {table}")
    
    # Verificar estructura de apartments
    print("\n" + "="*50)
    print("ESTRUCTURA DE LA TABLA 'apartments'")
    print("="*50)
    cur.execute("PRAGMA table_info(apartments)")
    columns = cur.fetchall()
    for col in columns:
        print(f"  {col[1]:20} {col[2]:15} {'NOT NULL' if col[3] else ''}")
    
    # Contar registros
    print("\n" + "="*50)
    print("CANTIDAD DE REGISTROS")
    print("="*50)
    for table in ['apartments', 'invoices', 'payments', 'recurring_sales']:
        if table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table:20} {count} registros")
    
    conn.close()
    print("\n✓ Verificación completada exitosamente")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    sys.exit(1)
