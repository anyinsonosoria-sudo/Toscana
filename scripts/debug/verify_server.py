#!/usr/bin/env python
"""
Script de verificación final: prueba todas las rutas del servidor
"""
import requests
import time

BASE_URL = "http://127.0.0.1:5000"

def test_route(path, description):
    """Probar una ruta específica"""
    try:
        response = requests.get(f"{BASE_URL}{path}", timeout=5)
        if response.status_code == 200:
            print(f"✅ {description:40} -> {path}")
            return True
        elif response.status_code == 302:
            print(f"↪️  {description:40} -> {path} (redirección)")
            return True
        else:
            print(f"❌ {description:40} -> {path} (código {response.status_code})")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ {description:40} -> No se puede conectar al servidor")
        return False
    except Exception as e:
        print(f"❌ {description:40} -> Error: {e}")
        return False

def main():
    """Función principal de verificación"""
    print("\n" + "="*80)
    print("VERIFICACIÓN FINAL DEL SERVIDOR WEB")
    print("="*80)
    print(f"URL Base: {BASE_URL}")
    print()
    
    # Esperar un momento para asegurar que el servidor esté listo
    print("Esperando que el servidor esté listo...")
    time.sleep(2)
    
    # Definir rutas a probar
    routes = [
        ("/", "Panel Informativo (Dashboard)"),
        ("/facturacion", "Facturación"),
        ("/gastos", "Gastos"),
        ("/contabilidad", "Contabilidad"),
        ("/servicios", "Reportes (Servicios)"),
        ("/configuracion", "Configuración"),
        ("/apartamentos", "Apartamentos (debe redirigir)"),
        ("/residentes", "Residentes (debe redirigir)"),
        ("/empresa", "Empresa (página antigua)"),
        ("/health", "Health Check"),
    ]
    
    print("\nProbando rutas:\n")
    results = []
    
    for path, description in routes:
        result = test_route(path, description)
        results.append(result)
        time.sleep(0.5)  # Pequeña pausa entre requests
    
    # Resumen
    print("\n" + "="*80)
    print("RESUMEN")
    print("="*80)
    
    passed = sum(1 for r in results if r)
    total = len(results)
    
    print(f"\nRutas probadas: {passed}/{total} funcionando correctamente")
    
    if passed == total:
        print("\n🎉 ¡TODAS LAS RUTAS FUNCIONAN CORRECTAMENTE!")
        print("\n✅ El servidor está listo para usar en http://127.0.0.1:5000")
        print("\nMenú de navegación actualizado:")
        print("  1. Panel Informativo (antes Dashboard)")
        print("  2. Facturación")
        print("  3. Gastos (nuevo)")
        print("  4. Contabilidad (nuevo)")
        print("  5. Reportes")
        print("  6. Configuración (consolidado: Empresa, Apartamentos, Residentes, Suplidores)")
    else:
        print("\n⚠️  Algunas rutas no están funcionando. Revisa los errores arriba.")
    
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nVerificación cancelada por el usuario.")
