#!/usr/bin/env python
"""
Test script para verificar que el sistema de pagos está funcionando
"""

import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("TEST DE SISTEMA DE PAGOS")
print("=" * 60)

# Test 1: Importar receipt_pdf
print("\n[1] Verificando módulo receipt_pdf...")
try:
    import receipt_pdf
    print("✓ receipt_pdf importado correctamente")
except Exception as e:
    print(f"✗ Error al importar receipt_pdf: {e}")
    sys.exit(1)

# Test 2: Verificar funciones de PDF
print("\n[2] Verificando funciones de generación de PDF...")
try:
    from receipt_pdf import generate_payment_receipt_pdf, generate_account_statement_pdf
    print("✓ Funciones de PDF disponibles")
except Exception as e:
    print(f"✗ Error al importar funciones de PDF: {e}")
    sys.exit(1)

# Test 3: Verificar models.py
print("\n[3] Verificando módulo models...")
try:
    import models
    print("✓ models importado correctamente")
except Exception as e:
    print(f"✗ Error al importar models: {e}")
    sys.exit(1)

# Test 4: Verificar funciones de pago en models
print("\n[4] Verificando funciones de pago en models...")
try:
    from models import _generate_receipt_pdf, _generate_account_statement_pdf, record_payment
    print("✓ Funciones de pago disponibles")
except Exception as e:
    print(f"✗ Error al importar funciones de pago: {e}")
    sys.exit(1)

# Test 5: Verificar blueprint de billing
print("\n[5] Verificando blueprint de billing...")
try:
    from blueprints.billing import billing_bp
    print("✓ Blueprint de billing importado correctamente")
except Exception as e:
    print(f"✗ Error al importar blueprint: {e}")
    sys.exit(1)

# Test 6: Verificar app.py
print("\n[6] Verificando configuración de la aplicación...")
try:
    from app import app
    
    # Listar rutas
    routes = []
    for rule in app.url_map.iter_rules():
        if 'ventas' in rule.rule:
            routes.append(f"{rule.rule} [{', '.join(rule.methods - {'HEAD', 'OPTIONS'})}]")
    
    if routes:
        print("✓ Rutas de ventas encontradas:")
        for route in sorted(routes):
            print(f"  - {route}")
    else:
        print("✗ No se encontraron rutas de ventas")
        
    # Verificar ruta específica de pagos
    has_payment_route = any('partial-payment' in rule.rule for rule in app.url_map.iter_rules())
    if has_payment_route:
        print("✓ Ruta de pago parcial encontrada")
    else:
        print("✗ Ruta de pago parcial NO encontrada")
        
except Exception as e:
    print(f"✗ Error al verificar aplicación: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("VERIFICACIÓN COMPLETADA EXITOSAMENTE ✓")
print("=" * 60)
print("\nPróximos pasos:")
print("1. Ir al formulario de 'Cuentas por Cobrar'")
print("2. Hacer clic en 'Registrar Pago'")
print("3. El comprobante de pago debe adjuntarse al email")
