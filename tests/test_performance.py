"""
Test: Performance Optimization - Fase 2.4
=========================================
Valida que las optimizaciones de performance estén funcionando.
"""

import sys
from pathlib import Path

# Agregar directorio al path
sys.path.insert(0, str(Path(__file__).parent))

def test_caching_import():
    """Verifica que Flask-Caching se importe correctamente"""
    print("\n[TEST 1] Importar Flask-Caching...")
    try:
        from flask_caching import Cache
        print("[OK] Flask-Caching importado")
        return True
    except ImportError as e:
        print(f"[ERROR] No se pudo importar Flask-Caching: {e}")
        return False


def test_extensions_cache():
    """Verifica que cache esté en extensions.py"""
    print("\n[TEST 2] Verificar cache en extensions...")
    try:
        from extensions import cache
        print(f"[OK] Cache disponible: {type(cache)}")
        return True
    except Exception as e:
        print(f"[ERROR] Error al importar cache: {e}")
        return False


def test_pagination_helper():
    """Verifica que el helper de paginación funcione"""
    print("\n[TEST 3] Verificar helper de paginación...")
    try:
        from utils.pagination import Pagination, paginate, get_page_range
        
        # Test básico
        items = list(range(1, 101))  # 100 items
        pagination = Pagination(items, page=1, per_page=20)
        
        print(f"[OK] Pagination creado")
        print(f"     Total items: {pagination.total}")
        print(f"     Páginas: {pagination.pages}")
        print(f"     Página actual: {pagination.page}")
        print(f"     Items en página 1: {len(pagination.items)}")
        
        # Validaciones
        assert pagination.total == 100, "Total incorrecto"
        assert pagination.pages == 5, "Páginas incorrectas"
        assert len(pagination.items) == 20, "Items por página incorrectos"
        assert pagination.items[0] == 1, "Primer item incorrecto"
        assert pagination.items[-1] == 20, "Último item incorrecto"
        
        # Test página 2
        pagination2 = Pagination(items, page=2, per_page=20)
        assert pagination2.items[0] == 21, "Página 2 incorrecta"
        assert pagination2.has_prev, "Debería tener página anterior"
        assert pagination2.has_next, "Debería tener página siguiente"
        
        print("[OK] Paginación funciona correctamente")
        return True
    except Exception as e:
        print(f"[ERROR] Error en paginación: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_db_optimizer():
    """Verifica que el optimizador de BD esté disponible"""
    print("\n[TEST 4] Verificar optimizador de BD...")
    try:
        from utils.db_optimizer import (
            create_indexes, 
            analyze_database,
            get_table_stats,
            get_index_stats
        )
        
        print("[OK] Funciones de optimización disponibles:")
        print("     - create_indexes")
        print("     - analyze_database")
        print("     - get_table_stats")
        print("     - get_index_stats")
        
        return True
    except Exception as e:
        print(f"[ERROR] Error al importar optimizador: {e}")
        return False


def test_blueprint_cache():
    """Verifica que el blueprint use cache"""
    print("\n[TEST 5] Verificar cache en apartments blueprint...")
    try:
        with open('blueprints/apartments.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = {
            'from extensions import cache': 'Importa cache',
            '@cache.cached': 'Usa decorador @cache.cached',
            'cache.delete_memoized': 'Invalida cache'
        }
        
        passed = 0
        for check, desc in checks.items():
            if check in content:
                print(f"[OK] {desc}")
                passed += 1
            else:
                print(f"[WARNING] No encontrado: {desc}")
        
        if passed == len(checks):
            print(f"[OK] Blueprint usa cache correctamente ({passed}/{len(checks)})")
            return True
        else:
            print(f"[WARNING] Algunas características de cache faltan ({passed}/{len(checks)})")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error al analizar blueprint: {e}")
        return False


def test_blueprint_pagination():
    """Verifica que el blueprint use paginación"""
    print("\n[TEST 6] Verificar paginación en apartments blueprint...")
    try:
        with open('blueprints/apartments.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = {
            'from utils.pagination import paginate': 'Importa paginate',
            'pagination = paginate': 'Crea paginación',
            'pagination.items': 'Usa items paginados'
        }
        
        passed = 0
        for check, desc in checks.items():
            if check in content:
                print(f"[OK] {desc}")
                passed += 1
            else:
                print(f"[WARNING] No encontrado: {desc}")
        
        if passed == len(checks):
            print(f"[OK] Blueprint usa paginación correctamente ({passed}/{len(checks)})")
            return True
        else:
            print(f"[WARNING] Algunas características de paginación faltan ({passed}/{len(checks)})")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error al analizar blueprint: {e}")
        return False


def test_requirements():
    """Verifica que Flask-Caching esté en requirements.txt"""
    print("\n[TEST 7] Verificar requirements.txt...")
    try:
        with open('requirements.txt', 'r', encoding='utf-8') as f:
            requirements = f.read()
        
        if 'Flask-Caching' in requirements:
            print("[OK] Flask-Caching está en requirements.txt")
            
            for line in requirements.split('\n'):
                if 'Flask-Caching' in line:
                    print(f"     {line.strip()}")
                    break
            return True
        else:
            print("[WARNING] Flask-Caching no está en requirements.txt")
            return False
        
    except FileNotFoundError:
        print("[WARNING] requirements.txt no encontrado")
        return False
    except Exception as e:
        print(f"[ERROR] Error al leer requirements.txt: {e}")
        return False


def test_app_initialization():
    """Verifica que la app inicialice cache"""
    print("\n[TEST 8] Verificar inicialización de cache...")
    try:
        from config import get_config
        from extensions import init_extensions, cache
        from flask import Flask
        
        # Crear app mínima
        app = Flask(__name__)
        config = get_config()
        app.config.from_object(config)
        
        # Inicializar extensiones
        init_extensions(app)
        
        print("[OK] Cache inicializado en la app")
        return True
    except Exception as e:
        print(f"[ERROR] Error al inicializar app: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Ejecuta todos los tests"""
    print("=" * 70)
    print("TEST: Performance Optimization - Fase 2.4")
    print("=" * 70)
    
    tests = [
        test_caching_import,
        test_extensions_cache,
        test_pagination_helper,
        test_db_optimizer,
        test_blueprint_cache,
        test_blueprint_pagination,
        test_requirements,
        test_app_initialization
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
        print("[OK] Performance optimization integrado correctamente")
        print("\n[INFO] Optimizaciones implementadas:")
        print("  - Flask-Caching: SimpleCache, 5 min timeout")
        print("  - Paginación: 20 items por página")
        print("  - DB Optimizer: Índices y estadísticas")
    else:
        print(f"\n[WARNING] {total - passed} test(s) fallaron")
        print("[INFO] Revisar errores arriba")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
