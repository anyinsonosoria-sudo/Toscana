"""
Script para ejecutar tests del sistema Building Maintenance
"""

import sys
import pytest

def main():
    """Ejecutar suite de tests"""
    print("\n" + "="*60)
    print(" BUILDING MAINTENANCE - TEST SUITE")
    print("="*60 + "\n")
    
    # Argumentos para pytest
    args = [
        '-v',  # Verbose
        '--tb=short',  # Traceback corto
        '-m', 'unit or integration',  # Solo tests unitarios e integración
        '--maxfail=5',  # Parar después de 5 fallos
        'tests/'
    ]
    
    # Ejecutar tests
    exit_code = pytest.main(args)
    
    print("\n" + "="*60)
    if exit_code == 0:
        print(" ✅ TODOS LOS TESTS PASARON")
    else:
        print(f" ❌ TESTS FALLIDOS (código: {exit_code})")
    print("="*60 + "\n")
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
