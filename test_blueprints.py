"""
Test de Blueprints
==================
Verifica que el sistema de blueprints funcione correctamente.
"""

import sys
from pathlib import Path

# Agregar el directorio principal al path
sys.path.insert(0, str(Path(__file__).parent))

print("🧪 Testing Blueprints...")
print("="  * 50)

# Test 1: Importar config
try:
    from config import get_config
    config = get_config()
    print("✅ Config importado correctamente")
    print(f"   - Base DIR: {config.BASE_DIR}")
    print(f"   - Debug: {config.DEBUG}")
except Exception as e:
    print(f"❌ Error importando config: {e}")
    sys.exit(1)

# Test 2: Importar extensions
try:
    from extensions import login_manager, csrf
    print("✅ Extensions importadas correctamente")
except Exception as e:
    print(f"❌ Error importando extensions: {e}")
    sys.exit(1)

# Test 3: Importar utils
try:
    from utils import role_required, admin_required, audit_log
    from utils import get_all_permissions
    from utils import save_upload_file, FileValidationError
    print("✅ Utils importados correctamente")
except Exception as e:
    print(f"❌ Error importando utils: {e}")
    sys.exit(1)

# Test 4: Importar blueprints
try:
    from blueprints.apartments import apartments_bp
    print("✅ Blueprint de apartamentos importado")
    print(f"   - Nombre: {apartments_bp.name}")
    print(f"   - Prefix: {apartments_bp.url_prefix}")
    print(f"   - Rutas registradas: {len(apartments_bp.deferred_functions)}")
except Exception as e:
    print(f"❌ Error importando blueprint de apartamentos: {e}")
    sys.exit(1)

# Test 5: Crear app de prueba
try:
    from flask import Flask
    from extensions import init_extensions
    
    app = Flask(__name__)
    app.config.from_object(config)
    
    # Inicializar extensiones
    init_extensions(app)
    
    # Registrar blueprint
    app.register_blueprint(apartments_bp)
    
    print("✅ App de prueba creada correctamente")
    print(f"   - Blueprints registrados: {list(app.blueprints.keys())}")
    
    # Mostrar rutas del blueprint
    print("\n📍 Rutas del blueprint 'apartments':")
    for rule in app.url_map.iter_rules():
        if 'apartments' in rule.endpoint:
            print(f"   - {rule.methods} {rule.rule} -> {rule.endpoint}")
    
except Exception as e:
    print(f"❌ Error creando app de prueba: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 50)
print("🎉 Todos los tests pasaron correctamente!")
print("✅ Sistema de blueprints listo para usar")
