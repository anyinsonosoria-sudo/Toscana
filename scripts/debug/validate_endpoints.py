"""
Script de validación completa de endpoints
Verifica que todos los url_for en templates apunten a endpoints válidos
"""
import re
from pathlib import Path
from importlib import import_module
import sys

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

def get_all_blueprint_endpoints():
    """Obtiene todos los endpoints de los blueprints"""
    endpoints = {
        # Auth endpoints (siempre presentes)
        'auth.login', 'auth.logout', 'auth.register', 'auth.index',
        'auth.change_password', 'auth.manage_users', 'auth.edit_user',
        'auth.delete_user', 'auth.manage_permissions', 'auth.update_permissions',
        'auth.list_users',  # Agregado
        'auth.deactivate_user',  # Agregado
        'auth.activate_user',  # Agregado
        'auth.manage_user_permissions',  # Agregado
        
        # Static
        'static',
    }
    
    # Blueprints registrados
    blueprint_files = [
        ('apartments', ['list', 'add', 'edit', 'delete']),
        ('suppliers', ['list', 'add', 'edit', 'delete']),
        ('products', ['list', 'add', 'edit', 'delete']),
        ('expenses', ['list', 'add', 'edit', 'delete', 'upload_ocr', 'save_with_receipt']),
        ('reports', ['list']),
        ('billing', [
            'invoices', 'payments', 'accounts_receivable', 'recurring_sales', 
            'register_payment', 'create_factura', 'edit_factura', 
            'delete_invoice', 'partial_payment', 'delete_payment',
            'create_recurring', 'toggle_recurring', 'generate_recurring', 
            'delete_recurring', 'view_invoice_pdf'
        ]),
        ('accounting', ['list', 'add', 'edit', 'delete']),
        ('company', ['view', 'update', 'delete_logo']),
    ]
    
    for blueprint, funcs in blueprint_files:
        for func in funcs:
            endpoints.add(f"{blueprint}.{func}")
    
    # Endpoints legacy (todavía en app.py)
    legacy_endpoints = [
        'add_residente', 'edit_residente', 'delete_residente',
        'add_servicio', 'edit_servicio', 'delete_servicio',
        'update_customization', 'update_sidebar_order',
        'view_units', 'add_unit',
        'index'  # Puede estar también en app.py
    ]
    endpoints.update(legacy_endpoints)
    
    return endpoints

def extract_url_for_from_template(file_path):
    """Extrae todos los url_for de un template"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Patrón para capturar url_for('endpoint')
    pattern = r"url_for\(['\"]([^'\"]+)['\"]"
    matches = re.findall(pattern, content)
    return set(matches)

def validate_templates():
    """Valida todos los templates"""
    templates_dir = Path(__file__).parent / 'templates'
    valid_endpoints = get_all_blueprint_endpoints()
    
    print("\n🔍 VALIDACIÓN DE ENDPOINTS EN TEMPLATES")
    print("="*70)
    
    all_errors = []
    all_ok = []
    
    for html_file in sorted(templates_dir.glob('*.html')):
        endpoints_in_template = extract_url_for_from_template(html_file)
        
        errors = []
        for endpoint in endpoints_in_template:
            if endpoint not in valid_endpoints:
                errors.append(endpoint)
        
        if errors:
            print(f"\n❌ {html_file.name}")
            for endpoint in errors:
                print(f"   • {endpoint} (NO EXISTE)")
                all_errors.append((html_file.name, endpoint))
        else:
            if endpoints_in_template:  # Solo si tiene endpoints
                print(f"✅ {html_file.name} ({len(endpoints_in_template)} endpoints)")
                all_ok.append(html_file.name)
    
    # Resumen
    print("\n" + "="*70)
    print("📊 RESUMEN DE VALIDACIÓN")
    print("="*70)
    print(f"✅ Templates correctos: {len(all_ok)}")
    print(f"❌ Templates con errores: {len(set([f for f, _ in all_errors]))}")
    print(f"🔴 Total endpoints inválidos: {len(all_errors)}")
    
    if all_errors:
        print("\n🔴 ENDPOINTS INVÁLIDOS ENCONTRADOS:")
        for filename, endpoint in all_errors:
            print(f"   {filename}: {endpoint}")
        
        print("\n⚠️  ACCIÓN REQUERIDA:")
        print("   1. Crear el endpoint en el blueprint correspondiente")
        print("   2. O actualizar el template para usar el endpoint correcto")
        print("   3. O agregar el endpoint a la lista legacy en este script")
        return False
    else:
        print("\n✅ Todos los templates están correctos!")
        return True

if __name__ == "__main__":
    success = validate_templates()
    sys.exit(0 if success else 1)
