"""
Reporte de problemas encontrados en la base de datos
"""
import sqlite3
from db import get_conn

print("=" * 80)
print("REPORTE DE ANÁLISIS DE LA BASE DE DATOS")
print("=" * 80)

conn = get_conn()
cur = conn.cursor()

# 1. Verificar residentes duplicados o con problemas
print("\n1. RESIDENTES Y APARTAMENTOS:")
print("-" * 80)
cur.execute("""
    SELECT r.id, r.name, r.role, r.unit_id, a.number as apartment_number
    FROM residents r
    LEFT JOIN apartments a ON r.unit_id = a.id
    ORDER BY a.number, r.role DESC
""")
rows = cur.fetchall()
print(f"{'ID':<5} {'Nombre':<25} {'Rol':<15} {'Unit_ID':<10} {'Apartamento':<15}")
print("-" * 80)
for row in rows:
    print(f"{row['id']:<5} {row['name']:<25} {row['role'] or 'N/A':<15} {row['unit_id'] or 'N/A':<10} {row['apartment_number'] or 'N/A':<15}")

# 2. Encontrar apartamentos con múltiples propietarios
print("\n2. APARTAMENTOS CON MÚLTIPLES PROPIETARIOS:")
print("-" * 80)
cur.execute("""
    SELECT a.number, COUNT(r.id) as num_propietarios, GROUP_CONCAT(r.name, ', ') as propietarios
    FROM apartments a
    JOIN residents r ON r.unit_id = a.id
    WHERE r.role = 'Propietario'
    GROUP BY a.id, a.number
    HAVING COUNT(r.id) > 1
""")
rows = cur.fetchall()
if rows:
    print("⚠️ PROBLEMA ENCONTRADO:")
    for row in rows:
        print(f"  • Apartamento {row['number']}: {row['num_propietarios']} propietarios")
        print(f"    Propietarios: {row['propietarios']}")
else:
    print("✓ No se encontraron apartamentos con múltiples propietarios")

# 3. Encontrar residentes con nombres similares o duplicados
print("\n3. RESIDENTES CON NOMBRES DUPLICADOS:")
print("-" * 80)
cur.execute("""
    SELECT name, COUNT(*) as count, GROUP_CONCAT(id) as ids
    FROM residents
    GROUP BY name
    HAVING COUNT(*) > 1
""")
rows = cur.fetchall()
if rows:
    print("⚠️ PROBLEMA ENCONTRADO:")
    for row in rows:
        print(f"  • Nombre: '{row['name']}' aparece {row['count']} veces (IDs: {row['ids']})")
else:
    print("✓ No se encontraron nombres duplicados")

# 4. Verificar apartamentos
print("\n4. TODOS LOS APARTAMENTOS:")
print("-" * 80)
cur.execute("""
    SELECT a.id, a.number, a.floor, 
           COUNT(r.id) as num_residentes,
           SUM(CASE WHEN r.role='Propietario' THEN 1 ELSE 0 END) as num_propietarios
    FROM apartments a
    LEFT JOIN residents r ON r.unit_id = a.id
    GROUP BY a.id
    ORDER BY a.number
""")
rows = cur.fetchall()
print(f"{'ID':<5} {'Número':<10} {'Piso':<15} {'Residentes':<12} {'Propietarios':<12}")
print("-" * 80)
for row in rows:
    flag = "⚠️" if row['num_propietarios'] > 1 else "✓"
    print(f"{flag} {row['id']:<5} {row['number']:<10} {row['floor'] or 'N/A':<15} {row['num_residentes']:<12} {row['num_propietarios']:<12}")

# 5. Verificar facturas
print("\n5. RESUMEN DE FACTURAS:")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as total_facturas,
        SUM(CASE WHEN paid=1 THEN 1 ELSE 0 END) as pagadas,
        SUM(CASE WHEN paid=0 THEN 1 ELSE 0 END) as pendientes,
        SUM(amount) as total_monto,
        SUM(CASE WHEN paid=1 THEN amount ELSE 0 END) as monto_pagado,
        SUM(CASE WHEN paid=0 THEN amount ELSE 0 END) as monto_pendiente
    FROM invoices
""")
row = cur.fetchone()
if row and row['total_facturas'] > 0:
    print(f"Total de facturas: {row['total_facturas']}")
    print(f"Pagadas: {row['pagadas']}")
    print(f"Pendientes: {row['pendientes']}")
    print(f"Monto total: ${row['total_monto']:.2f}")
    print(f"Monto pagado: ${row['monto_pagado']:.2f}")
    print(f"Monto pendiente: ${row['monto_pendiente']:.2f}")
else:
    print("No hay facturas registradas")

conn.close()

print("\n" + "=" * 80)
print("REPORTE COMPLETADO")
print("=" * 80)
