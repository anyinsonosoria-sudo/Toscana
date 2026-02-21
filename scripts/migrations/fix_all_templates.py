"""
Script para auditar y corregir TODOS los url_for en templates
Mapea automáticamente endpoints legacy a blueprints
"""
import re
from pathlib import Path

# Mapeo completo de endpoints legacy -> blueprint
ENDPOINT_MAP = {
    # Index
    'index': 'auth.index',
    
    # Billing (facturacion.html, cuentas_cobrar.html, etc.)
    'create_factura': 'billing.create_invoice',  # Corregido: la función es create_invoice
    'edit_factura': 'billing.edit_invoice',  # Corregido: la función es edit_invoice
    'view_invoice_pdf': 'billing.view_invoice_pdf',
    'view_facturacion': 'billing.invoices',
    'create_recurring_sale': 'billing.create_recurring',
    'view_invoices': 'billing.invoices',
    'create_invoice': 'billing.create_invoice',
    'record_payment': 'billing.register_payment',
    
    # Apartments (apartamentos.html, configuracion.html)
    'add_apartamento': 'apartments.add',
    'edit_apartamento': 'apartments.edit',
    'delete_apartamento': 'apartments.delete',
    
    # Products/Services (productos.html, configuracion.html)
    'add_product_service': 'products.add',
    'edit_product_service': 'products.edit',
    'delete_product_service': 'products.delete',
    'products.list': 'products.list',  # Ya correcto
    
    # Suppliers (suplidores.html, configuracion.html)
    'add_supplier': 'suppliers.add',
    'edit_supplier': 'suppliers.edit',
    'delete_supplier': 'suppliers.delete',
    
    # Expenses (gastos.html)
    'add_expense': 'expenses.add',
    'edit_expense': 'expenses.edit',
    'delete_expense': 'expenses.delete',
    'upload_receipt_ocr': 'expenses.upload_ocr',
    'save_expense_with_receipt': 'expenses.save_with_receipt',
    
    # Residents (residentes.html) - NO MIGRADO AÚN
    'add_residente': 'add_residente',  # Mantener legacy
    'edit_residente': 'edit_residente',  # Mantener legacy
    'delete_residente': 'delete_residente',  # Mantener legacy
    
    # Services (servicios.html) - NO MIGRADO AÚN
    'add_servicio': 'add_servicio',  # Mantener legacy
    'edit_servicio': 'edit_servicio',  # Mantener legacy
    'delete_servicio': 'delete_servicio',  # Mantener legacy
    
    # Company/Configuration (configuracion.html, empresa.html)
    'update_company_info': 'company.update',
    'update_customization': 'update_customization',  # Mantener legacy
    'update_sidebar_order': 'update_sidebar_order',  # Mantener legacy
    
    # Units - NO MIGRADO
    'view_units': 'view_units',  # Mantener legacy
    'add_unit': 'add_unit',  # Mantener legacy
}

def fix_template(file_path):
    """Corrige todos los url_for en un template"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes = []
    
    # Patrón para capturar url_for('endpoint', ...)
    pattern = r"url_for\(['\"]([^'\"]+)['\"]"
    
    def replace_endpoint(match):
        old_endpoint = match.group(1)
        
        # Si ya tiene blueprint prefix o es static, no cambiar
        if '.' in old_endpoint or old_endpoint == 'static' or old_endpoint.startswith('_'):
            return match.group(0)
        
        # Buscar en el mapeo
        new_endpoint = ENDPOINT_MAP.get(old_endpoint, old_endpoint)
        
        if new_endpoint != old_endpoint:
            changes.append(f"  {old_endpoint} → {new_endpoint}")
            return f"url_for('{new_endpoint}'"
        
        return match.group(0)
    
    content = re.sub(pattern, replace_endpoint, content)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return changes
    
    return []

def audit_templates():
    """Audita y corrige todos los templates"""
    templates_dir = Path(__file__).parent / 'templates'
    
    if not templates_dir.exists():
        print("❌ No se encontró la carpeta templates/")
        return
    
    html_files = list(templates_dir.glob('*.html'))
    
    print(f"\n🔍 Auditando {len(html_files)} archivos HTML...\n")
    print("="*70)
    
    total_changes = 0
    files_changed = 0
    files_ok = 0
    
    for html_file in sorted(html_files):
        changes = fix_template(html_file)
        
        if changes:
            files_changed += 1
            total_changes += len(changes)
            print(f"\n🔧 {html_file.name}")
            for change in changes:
                print(change)
        else:
            files_ok += 1
            print(f"✅ {html_file.name}")
    
    # Resumen
    print("\n" + "="*70)
    print("📊 RESUMEN DE AUDITORÍA")
    print("="*70)
    print(f"✅ Sin cambios: {files_ok} archivos")
    print(f"🔧 Corregidos: {files_changed} archivos")
    print(f"📝 Total cambios: {total_changes} endpoints actualizados")
    
    if files_changed > 0:
        print("\n⚠️  IMPORTANTE: Reinicia el servidor Flask para que los cambios surtan efecto.")
        print("\n📌 ENDPOINTS NO MIGRADOS (aún en app.py):")
        print("   • Residentes: add_residente, edit_residente, delete_residente")
        print("   • Servicios: add_servicio, edit_servicio, delete_servicio")
        print("   • Customization: update_customization, update_sidebar_order")
        print("   • Units: view_units, add_unit")
        print("\n💡 Estos endpoints deben migrarse a blueprints para completar la refactorización.")
    else:
        print("\n✅ Todos los templates están correctos.")
    
    print("\n✅ Auditoría completada.\n")

if __name__ == "__main__":
    audit_templates()
