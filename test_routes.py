#!/usr/bin/env python
"""Test para verificar las rutas registradas"""

from app import create_app

app = create_app()

print("\n" + "="*70)
print("VERIFICANDO RUTAS DE LA APLICACIÓN")
print("="*70)

print("\n✓ Rutas que contienen 'partial-payment':")
encontradas = False
for rule in app.url_map.iter_rules():
    if 'partial-payment' in str(rule):
        print(f"  {rule}")
        encontradas = True

if not encontradas:
    print("  ❌ NO SE ENCONTRÓ NINGUNA RUTA CON 'partial-payment'")

print("\n✓ Rutas que contienen 'facturas':")
encontradas = False
for rule in app.url_map.iter_rules():
    if 'facturas' in str(rule):
        print(f"  {rule}")
        encontradas = True

if not encontradas:
    print("  ❌ NO SE ENCONTRÓ NINGUNA RUTA CON 'facturas'")

print("\n✓ Rutas que contienen 'ventas':")
encontradas = False
for rule in app.url_map.iter_rules():
    if 'ventas' in str(rule):
        print(f"  {rule}")
        encontradas = True

if not encontradas:
    print("  ❌ NO SE ENCONTRÓ NINGUNA RUTA CON 'ventas'")

print("\n✓ Todas las rutas POST:")
for rule in app.url_map.iter_rules():
    if 'POST' in str(rule.methods):
        print(f"  {rule}")

print("\n" + "="*70)
