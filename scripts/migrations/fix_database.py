"""
Script para corregir problemas en la base de datos
"""
from db import get_conn

print("=" * 80)
print("CORRECCIÓN DE PROBLEMAS EN LA BASE DE DATOS")
print("=" * 80)

conn = get_conn()
cur = conn.cursor()

# Problema 1: Apartamento 1A tiene 2 propietarios (Williams Osoria ID:1 y Carlos Rodríguez ID:3)
print("\n1. Analizando apartamento 1A con múltiples propietarios...")
cur.execute("""
    SELECT id, name, role, email, phone, created_at
    FROM residents
    WHERE unit_id = 1 AND role = 'Propietario'
    ORDER BY id
""")
propietarios = cur.fetchall()

if len(propietarios) > 1:
    print(f"   Encontrados {len(propietarios)} propietarios:")
    for p in propietarios:
        print(f"   • ID {p['id']}: {p['name']} (Creado: {p['created_at']})")
    
    # El más antiguo es Williams Osoria (ID: 1), lo mantendremos
    # Carlos Rodríguez (ID: 3) debería moverse
    print("\n   ACCIÓN RECOMENDADA:")
    print(f"   - Mantener a '{propietarios[0]['name']}' (ID: {propietarios[0]['id']}) como propietario de 1A")
    print(f"   - Cambiar el rol de '{propietarios[1]['name']}' (ID: {propietarios[1]['id']}) a 'Inquilino'")
    print("     O eliminar el registro duplicado si es un error de captura")

# Problema 2: Carlos Rodríguez aparece 2 veces (ID: 3 y 4)
print("\n2. Analizando nombre duplicado 'Carlos Rodríguez'...")
cur.execute("""
    SELECT r.id, r.name, r.role, r.unit_id, a.number as apartment_number, r.created_at
    FROM residents r
    LEFT JOIN apartments a ON r.unit_id = a.id
    WHERE r.name = 'Carlos Rodríguez'
    ORDER BY r.id
""")
duplicados = cur.fetchall()

if len(duplicados) > 1:
    print(f"   Encontrados {len(duplicados)} registros con el mismo nombre:")
    for d in duplicados:
        print(f"   • ID {d['id']}: Apartamento {d['apartment_number']}, Rol: {d['role']} (Creado: {d['created_at']})")
    
    print("\n   ACCIÓN RECOMENDADA:")
    print("   - Si son la misma persona, eliminar uno de los registros")
    print("   - Si son personas diferentes, agregar un diferenciador al nombre")

print("\n" + "=" * 80)
print("OPCIONES DE CORRECCIÓN")
print("=" * 80)
print("\nOpción A - Corrección Automática (Recomendada):")
print("  1. Cambiar Carlos Rodríguez (ID:3) de Propietario a Inquilino en 1A")
print("  2. Mantener Carlos Rodríguez (ID:4) como Propietario de 101")
print("")
print("Opción B - Corrección Manual:")
print("  1. Eliminar registro duplicado de Carlos Rodríguez (ID:3)")
print("  2. Mantener solo Carlos Rodríguez (ID:4) como Propietario de 101")
print("")

respuesta = input("¿Desea aplicar la corrección automática (Opción A)? (s/n): ")

if respuesta.lower() == 's':
    print("\nAplicando correcciones...")
    try:
        # Cambiar rol de Carlos Rodríguez (ID:3) a Inquilino
        cur.execute("UPDATE residents SET role='Inquilino' WHERE id=3")
        conn.commit()
        print("✓ Carlos Rodríguez (ID:3) cambiado a Inquilino en apartamento 1A")
        
        print("\n✓ Correcciones aplicadas exitosamente")
        print("\nEstado actualizado:")
        print("-" * 80)
        
        # Mostrar estado actualizado
        cur.execute("""
            SELECT a.number, r.name, r.role
            FROM apartments a
            JOIN residents r ON r.unit_id = a.id
            ORDER BY a.number, r.role DESC
        """)
        rows = cur.fetchall()
        for row in rows:
            print(f"  Apartamento {row['number']}: {row['name']} ({row['role']})")
        
    except Exception as e:
        print(f"❌ Error al aplicar correcciones: {e}")
        conn.rollback()
else:
    print("\nNo se aplicaron cambios. Puede corregir manualmente desde la interfaz web.")

conn.close()
print("\n" + "=" * 80)
