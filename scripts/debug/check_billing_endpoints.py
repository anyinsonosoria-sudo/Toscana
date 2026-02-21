"""
Script para agregar endpoints explícitos a las rutas del blueprint de billing
"""
from pathlib import Path
import re

def fix_billing_blueprint():
    """Agregar endpoints explícitos a todas las rutas"""
    file_path = Path(__file__).parent / 'blueprints' / 'billing.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Mapeo de rutas a endpoints esperados
    route_endpoint_map = [
        # (ruta_pattern, endpoint_name)
        (r"@billing_bp\.route\('/facturacion'\)", "invoices"),  # Ya correcto, solo documentar
        (r"@billing_bp\.route\('/facturacion/create'", "create_factura"),  # Ya agregado
        (r"@billing_bp\.route\('/facturacion/edit/<int:invoice_id>'", "edit_factura"),  # Ya agregado
        (r"@billing_bp\.route\('/facturacion/pdf/<int:invoice_id>'", "view_invoice_pdf"),  # Nuevo
    ]
    
    changes = []
    
    for pattern, endpoint in route_endpoint_map:
        # Verificar si ya tiene endpoint
        if f"endpoint='{endpoint}'" in content:
            print(f"✅ Endpoint '{endpoint}' ya existe")
            continue
        
        # Buscar la ruta
        match = re.search(pattern, content)
        if match:
            # Verificar si la ruta ya tiene endpoint= (aunque sea distinto)
            line_start = content.rfind('\n', 0, match.start()) + 1
            line_end = content.find('\n', match.start())
            line = content[line_start:line_end]
            
            if 'endpoint=' in line:
                print(f"⚠️  Ruta {pattern} ya tiene un endpoint diferente")
                continue
            
            # Buscar el final del decorator (antes del paréntesis de cierre)
            decorator_end = content.find(')', match.end())
            if decorator_end != -1:
                # Verificar si tiene methods=
                if ', methods=' in content[match.start():decorator_end]:
                    # Agregar después de methods
                    insert_pos = content.find(')', decorator_end - 20)  # Buscar hacia atrás
                    new_text = f", endpoint='{endpoint}'"
                else:
                    # Agregar antes del cierre
                    insert_pos = decorator_end
                    new_text = f", endpoint='{endpoint}'"
                
                # Realizar el reemplazo
                # Esta es una aproximación, mejor hacerlo manualmente por seguridad
                print(f"🔧 Se necesita agregar endpoint='{endpoint}' a {pattern}")
                changes.append(endpoint)
        else:
            print(f"❓ No se encontró ruta para {pattern}")
    
    print(f"\n📊 Total de cambios sugeridos: {len(changes)}")
    if changes:
        print("⚠️  Los siguientes endpoints necesitan ser agregados manualmente:")
        for ep in changes:
            print(f"   • {ep}")

if __name__ == "__main__":
    fix_billing_blueprint()
