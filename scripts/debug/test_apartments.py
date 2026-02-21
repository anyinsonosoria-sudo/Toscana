"""
Script de prueba: Verificar que apartments se crean y listan correctamente
"""
import sys
from pathlib import Path

# Agregar el directorio padre al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import db
import apartments

def main():
    print("="*60)
    print("PRUEBA DE APARTAMENTOS - VERIFICACIÓN COMPLETA")
    print("="*60)
    
    # 1. Verificar la ruta de la base de datos
    print(f"\n[1] Ruta de la base de datos: {db.DB_PATH}")
    print(f"    ¿Existe? {db.DB_PATH.exists()}")
    
    # 2. Listar apartamentos existentes
    print("\n[2] Apartamentos existentes en la base de datos:")
    existing_apts = apartments.list_apartments()
    if existing_apts:
        for apt in existing_apts:
            print(f"    - ID: {apt['id']}, Número: {apt['number']}, Residente: {apt.get('resident_name', 'N/A')}")
    else:
        print("    (No hay apartamentos)")
    
    # 3. Intentar crear un apartamento de prueba
    print("\n[3] Creando apartamento de prueba...")
    try:
        test_number = "TEST-101"
        # Verificar si ya existe
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM apartments WHERE number=?", (test_number,))
        existing = cur.fetchone()
        conn.close()
        
        if existing:
            print(f"    ⚠️  Ya existe apartamento {test_number}, eliminándolo primero...")
            apartments.delete_apartment(existing['id'])
        
        new_id = apartments.add_apartment(
            number=test_number,
            floor="1",
            notes="Apartamento de prueba creado por script de debug",
            resident_name="Residente de Prueba",
            resident_role="tenant",
            resident_email="test@example.com",
            resident_phone="123-456-7890",
            payment_terms=30
        )
        print(f"    ✓ Apartamento creado con ID: {new_id}")
    except Exception as e:
        print(f"    ✗ Error al crear apartamento: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. Verificar que se puede listar
    print("\n[4] Listando todos los apartamentos después de la creación:")
    all_apts = apartments.list_apartments()
    print(f"    Total: {len(all_apts)} apartamento(s)")
    for apt in all_apts:
        print(f"    - ID: {apt['id']}, Número: {apt['number']}, Residente: {apt.get('resident_name', 'N/A')}")
    
    # 5. Verificar directamente en la base de datos
    print("\n[5] Consulta directa a la base de datos:")
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as count FROM apartments")
        count_result = cur.fetchone()
        print(f"    Total en DB: {count_result['count']} apartamento(s)")
        
        cur.execute("SELECT id, number, resident_name FROM apartments")
        db_apts = cur.fetchall()
        for apt in db_apts:
            print(f"    - DB: ID={apt['id']}, Number={apt['number']}, Resident={apt['resident_name']}")
        conn.close()
    except Exception as e:
        print(f"    ✗ Error al consultar DB: {e}")
    
    print("\n" + "="*60)
    print("CONCLUSIÓN:")
    if len(all_apts) > 0:
        print("✓ Los apartamentos se están creando y listando correctamente.")
        print("✓ La base de datos funciona bien.")
        print("\n⚠️  Si aún no ves apartamentos en la web, el problema está en:")
        print("   1. El servidor Flask no se reinició después de los cambios")
        print("   2. Estás visitando una URL incorrecta")
        print("   3. Hay un problema con la sesión del navegador")
        print("\nACCIONES RECOMENDADAS:")
        print("1. Reinicia el servidor Flask (Ctrl+C y vuelve a ejecutar app.py)")
        print("2. Visita http://127.0.0.1:5000/apartamentos/")
        print("3. Revisa la terminal del servidor para el mensaje:")
        print("   [DEBUG] ===== APARTMENTS LIST ROUTE ACCESSED =====")
    else:
        print("✗ No se pudieron crear apartamentos. Hay un problema con la base de datos.")
    print("="*60)

if __name__ == "__main__":
    main()
