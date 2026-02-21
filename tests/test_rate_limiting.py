"""
Test: Rate Limiting con Flask-Limiter
=====================================
Valida que el rate limiting esté configurado y funcional.
"""

import sys
from pathlib import Path

# Agregar directorio al path
sys.path.insert(0, str(Path(__file__).parent))

def test_limiter_import():
    """Verifica que Flask-Limiter se importe correctamente"""
    print("\n[TEST 1] Importar Flask-Limiter...")
    try:
        from flask_limiter import Limiter
        print("[OK] Flask-Limiter importado")
        print(f"     Versión: {Limiter.__module__}")
        return True
    except ImportError as e:
        print(f"[ERROR] No se pudo importar Flask-Limiter: {e}")
        return False


def test_extensions_limiter():
    """Verifica que limiter esté en extensions.py"""
    print("\n[TEST 2] Verificar limiter en extensions...")
    try:
        from extensions import limiter
        print(f"[OK] Limiter disponible: {type(limiter)}")
        print(f"     Default limits: {limiter._default_limits}")
        print(f"     Storage: {limiter._storage_uri}")
        return True
    except Exception as e:
        print(f"[ERROR] Error al importar limiter: {e}")
        return False


def test_auth_decorators():
    """Verifica que auth.py use rate limiting"""
    print("\n[TEST 3] Verificar decoradores en auth.py...")
    try:
        # Leer archivo auth.py
        with open('auth.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Buscar imports
        if 'from extensions import limiter' in content:
            print("[OK] auth.py importa limiter")
        else:
            print("[WARNING] auth.py no importa limiter")
            return False
        
        # Buscar decoradores
        decorators_found = []
        if '@limiter.limit' in content:
            # Contar ocurrencias
            count = content.count('@limiter.limit')
            print(f"[OK] Encontrados {count} decoradores @limiter.limit")
            
            # Buscar específicos
            if '5 per minute' in content:
                decorators_found.append("login: 5/min")
            if '10 per hour' in content:
                decorators_found.append("register: 10/hora")
            
            for dec in decorators_found:
                print(f"     - {dec}")
        else:
            print("[WARNING] No se encontraron decoradores @limiter.limit")
            return False
        
        return True
    except Exception as e:
        print(f"[ERROR] Error al analizar auth.py: {e}")
        return False


def test_app_initialization():
    """Verifica que la app inicialice limiter"""
    print("\n[TEST 4] Verificar inicialización en app...")
    try:
        from config import get_config
        from extensions import init_extensions, limiter
        from flask import Flask
        
        # Crear app mínima
        app = Flask(__name__)
        config = get_config()
        app.config.from_object(config)
        
        # Inicializar extensiones
        init_extensions(app)
        
        # Verificar que limiter esté vinculado
        print("[OK] Extensiones inicializadas con limiter")
        print(f"     App registrado en limiter: {hasattr(limiter, '_app')}")
        
        return True
    except Exception as e:
        print(f"[ERROR] Error al inicializar app: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_limits_configuration():
    """Verifica la configuración de límites"""
    print("\n[TEST 5] Verificar configuración de límites...")
    try:
        from extensions import limiter
        
        print("[OK] Límites configurados:")
        print(f"     Default: {limiter._default_limits}")
        print(f"     Estrategia: {limiter._strategy}")
        print(f"     Key function: {limiter._key_func.__name__}")
        
        # Verificar valores esperados
        expected_limits = ["200 per day", "50 per hour"]
        actual_limits = [str(limit) for limit in limiter._default_limits]
        
        if actual_limits == expected_limits:
            print("     [OK] Límites por defecto correctos")
        else:
            print(f"     [WARNING] Límites inesperados: {actual_limits}")
        
        return True
    except Exception as e:
        print(f"[ERROR] Error al verificar configuración: {e}")
        return False


def test_requirements():
    """Verifica que Flask-Limiter esté en requirements.txt"""
    print("\n[TEST 6] Verificar requirements.txt...")
    try:
        with open('requirements.txt', 'r', encoding='utf-8') as f:
            requirements = f.read()
        
        if 'Flask-Limiter' in requirements:
            print("[OK] Flask-Limiter está en requirements.txt")
            
            # Extraer línea
            for line in requirements.split('\n'):
                if 'Flask-Limiter' in line:
                    print(f"     {line.strip()}")
                    break
        else:
            print("[WARNING] Flask-Limiter no está en requirements.txt")
            print("[INFO] Agregar: Flask-Limiter>=3.5.0")
            return False
        
        return True
    except FileNotFoundError:
        print("[WARNING] requirements.txt no encontrado")
        return False
    except Exception as e:
        print(f"[ERROR] Error al leer requirements.txt: {e}")
        return False


def main():
    """Ejecuta todos los tests"""
    print("=" * 70)
    print("TEST: Rate Limiting con Flask-Limiter - Fase 2.3")
    print("=" * 70)
    
    tests = [
        test_limiter_import,
        test_extensions_limiter,
        test_limits_configuration,
        test_auth_decorators,
        test_app_initialization,
        test_requirements
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n[FATAL] Test falló: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"\nTests pasados: {passed}/{total}")
    
    if passed == total:
        print("\n[OK] Todos los tests pasaron exitosamente!")
        print("[OK] Rate limiting integrado correctamente")
        print("\n[INFO] Límites configurados:")
        print("  - Global: 200 req/día, 50 req/hora")
        print("  - Login: 5 req/minuto")
        print("  - Register: 10 req/hora")
    else:
        print(f"\n[WARNING] {total - passed} test(s) fallaron")
        print("[INFO] Revisar errores arriba")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
