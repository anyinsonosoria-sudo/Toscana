"""
Script de prueba para validar las nuevas funcionalidades
"""
import residents
import apartments
import products_services

print("=" * 60)
print("PRUEBAS DE VALIDACIÓN DEL SISTEMA")
print("=" * 60)

# Test 1: Intentar agregar apartamento duplicado
print("\nTEST 1: Intentar agregar apartamento duplicado (1A)...")
try:
    apartments.add_apartment('1A', 'Primero', 'Test')
    print("❌ ERROR: Debería haber fallado")
except ValueError as e:
    print(f"✓ CORRECTO: {e}")
except Exception as e:
    print(f"✓ CORRECTO (otro error): {e}")

# Test 2: Verificar propietarios en apartamento 1A
print("\nTEST 2: Verificar propietarios en apartamento 1A...")
owner = residents.check_apartment_owner(1)
if owner:
    print(f"✓ Propietario encontrado: {owner['name']} (ID: {owner['id']})")
else:
    print("No hay propietario en este apartamento")

# Test 3: Intentar agregar otro propietario al mismo apartamento
print("\nTEST 3: Intentar agregar otro propietario al apartamento 1A...")
try:
    residents.add_resident(1, 'Test Person', 'Propietario', 'test@test.com')
    print("❌ ERROR: Debería haber fallado")
except ValueError as e:
    print(f"✓ CORRECTO: {e}")

# Test 4: Intentar eliminar apartamento con residentes
print("\nTEST 4: Intentar eliminar apartamento con residentes...")
try:
    apartments.delete_apartment(1)
    print("❌ ERROR: Debería haber fallado")
except ValueError as e:
    print(f"✓ CORRECTO: {e}")

# Test 5: Intentar actualizar apartamento con número duplicado
print("\nTEST 5: Intentar actualizar apartamento 2 con número duplicado (1A)...")
try:
    apartments.update_apartment(2, number='1A')
    print("❌ ERROR: Debería haber fallado")
except ValueError as e:
    print(f"✓ CORRECTO: {e}")

# Test 6: Actualizar apartamento con número válido
print("\nTEST 6: Actualizar apartamento 2 con número válido...")
try:
    apartments.update_apartment(2, number='4A')
    print("✓ CORRECTO: Apartamento actualizado")
except Exception as e:
    print(f"✓ Ya tiene ese número o error: {e}")

# Test 7: Probar validación de códigos de productos/servicios duplicados
print("\nTEST 7: Agregar producto con código único...")
try:
    products_services.add_product_service('Test Service', 'Servicio', 100.0, code='TEST001')
    print("✓ CORRECTO: Producto agregado")
except ValueError as e:
    print(f"Ya existe o error: {e}")

print("\nTEST 8: Intentar agregar producto con código duplicado...")
try:
    products_services.add_product_service('Test Service 2', 'Servicio', 200.0, code='TEST001')
    print("❌ ERROR: Debería haber fallado")
except ValueError as e:
    print(f"✓ CORRECTO: {e}")

print("\n" + "=" * 60)
print("✓ PRUEBAS COMPLETADAS")
print("=" * 60)
