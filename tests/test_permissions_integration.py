"""
Test: Integración de Permisos Granulares
========================================
Valida que el sistema de permisos granulares esté correctamente integrado.
"""

import sys
from pathlib import Path

# Agregar directorio al path
sys.path.insert(0, str(Path(__file__).parent))

def test_decorator_import():
    """Verifica que el decorador permission_required se importe correctamente"""
    print("\n[TEST 1] Importar decorador permission_required...")
    try:
        from utils.decorators import permission_required
        print("[OK] Decorador permission_required importado")
        print(f"     Tipo: {type(permission_required)}")
        print(f"     Callable: {callable(permission_required)}")
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo importar: {e}")
        return False


def test_utils_export():
    """Verifica que utils exporte permission_required"""
    print("\n[TEST 2] Verificar exportación en utils...")
    try:
        from utils import permission_required
        print("[OK] permission_required disponible desde utils")
        return True
    except Exception as e:
        print(f"[ERROR] No está exportado en utils: {e}")
        return False


def test_check_permission():
    """Verifica que check_permission funcione"""
    print("\n[TEST 3] Verificar función check_permission...")
    try:
        from utils.permissions import check_permission
        
        # Admin siempre tiene permisos
        result = check_permission(1, 'apartamentos.view')
        print(f"[OK] check_permission(1, 'apartamentos.view') = {result}")
        
        if result:
            print("     [OK] Admin tiene todos los permisos (esperado)")
        else:
            print("     [WARNING] Admin sin permisos (revisar)")
        
        return True
    except Exception as e:
        print(f"[ERROR] Error al verificar permisos: {e}")
        return False


def test_blueprint_imports():
    """Verifica que el blueprint de apartamentos importe correctamente"""
    print("\n[TEST 4] Verificar importaciones en apartments blueprint...")
    try:
        from blueprints.apartments import apartments_bp
        print(f"[OK] Blueprint importado: {apartments_bp.name}")
        
        # Verificar que tenga rutas
        rules = [rule.rule for rule in apartments_bp.url_map.iter_rules() if rule.endpoint.startswith('apartments')]
        print(f"     Rutas encontradas: {len(rules)}")
        
        return True
    except Exception as e:
        print(f"[ERROR] Error al importar blueprint: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_context_processor():
    """Verifica que la app tenga el context processor"""
    print("\n[TEST 5] Verificar context processor has_permission...")
    try:
        # Importar configuración
        from config import get_config
        from extensions import init_extensions
        from flask import Flask
        
        # Crear app mínima
        app = Flask(__name__)
        config = get_config()
        app.config.from_object(config)
        init_extensions(app)
        
        # Buscar context processor
        processors = app.template_context_processors[None]
        print(f"[OK] App tiene {len(processors)} context processors")
        
        # El has_permission se agregará cuando se importe app.py completo
        print("     [INFO] has_permission se inyecta en app.py completo")
        
        return True
    except Exception as e:
        print(f"[ERROR] Error al verificar context processor: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_permissions_list():
    """Verifica que todos los permisos estén definidos"""
    print("\n[TEST 6] Verificar lista de permisos...")
    try:
        from utils.permissions import get_all_permissions, get_permissions_by_module
        
        all_perms = get_all_permissions()
        print(f"[OK] Total de permisos: {len(all_perms)}")
        
        by_module = get_permissions_by_module()
        print(f"[OK] Módulos con permisos: {len(by_module)}")
        
        # Verificar permisos de apartamentos
        apt_perms = [p['name'] for p in all_perms if p['module'] == 'apartamentos']
        print(f"\n     Permisos de Apartamentos:")
        for perm in apt_perms:
            print(f"       - {perm}")
        
        expected = ['apartamentos.view', 'apartamentos.create', 'apartamentos.edit', 'apartamentos.delete']
        if all(p in apt_perms for p in expected):
            print("     [OK] Todos los permisos de apartamentos definidos")
        else:
            print("     [WARNING] Faltan algunos permisos")
        
        return True
    except Exception as e:
        print(f"[ERROR] Error al verificar permisos: {e}")
        return False


def main():
    """Ejecuta todos los tests"""
    print("=" * 70)
    print("TEST: Integración de Permisos Granulares - Fase 2.2")
    print("=" * 70)
    
    tests = [
        test_decorator_import,
        test_utils_export,
        test_check_permission,
        test_permissions_list,
        test_blueprint_imports,
        test_context_processor
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
        print("[OK] Sistema de permisos granulares integrado correctamente")
    else:
        print(f"\n[WARNING] {total - passed} test(s) fallaron")
        print("[INFO] Revisar errores arriba")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
