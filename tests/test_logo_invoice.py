"""
Script para probar la generación de facturas con logo
"""
import invoice_pdf
import company
from pathlib import Path

# Obtener información de la empresa
company_info = company.get_company_info()

if not company_info:
    print("⚠️  No hay información de empresa configurada")
    company_info = {
        'name': 'Empresa de Prueba',
        'address': 'Calle Principal 123',
        'city': 'Santo Domingo',
        'country': 'República Dominicana',
        'phone': '809-555-1234',
        'email': 'admin@empresa.com',
        'bank_account': '1234567890',
        'logo_path': None
    }
else:
    print(f"✓ Información de empresa: {company_info['name']}")
    if company_info.get('logo_path'):
        logo_path = Path(__file__).parent / 'static' / 'uploads' / company_info['logo_path']
        if logo_path.exists():
            print(f"✓ Logo encontrado: {company_info['logo_path']}")
        else:
            print(f"⚠️  Logo configurado pero archivo no existe: {company_info['logo_path']}")
    else:
        print("ℹ️  No hay logo configurado")

# Datos de factura de prueba
invoice_data = {
    'id': 9999,
    'description': 'Mantenimiento Mensual - Cuota de Enero 2026',
    'amount': 5000.00,
    'issued_date': 'January 09, 2026',
    'due_date': 'January 31, 2026',
    'apartment_number': 'A-101',
    'resident_name': 'Juan Pérez',
    'resident_email': 'juan.perez@email.com',
    'resident_phone': '809-123-4567',
    'notes': 'Pago mensual de servicios comunes'
}

# Generar PDF de prueba
output_dir = Path(__file__).parent / "static" / "invoices"
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "test_invoice_with_logo.pdf"

print("\n" + "=" * 60)
print("GENERANDO FACTURA DE PRUEBA CON LOGO")
print("=" * 60)

try:
    invoice_pdf.generate_invoice_pdf(invoice_data, company_info, str(output_path))
    print(f"\n✓ PDF generado exitosamente:")
    print(f"  📄 {output_path}")
    print(f"\n✓ Características:")
    print(f"  - Formato de moneda: RD$ 5,000.00")
    print(f"  - Logo en encabezado: {'SÍ' if company_info.get('logo_path') else 'NO'}")
    print(f"  - Logo en pie de página: {'SÍ' if company_info.get('logo_path') else 'NO'}")
    print(f"\nℹ️  Abre el archivo para verificar el diseño")
except Exception as e:
    print(f"\n✗ Error al generar PDF: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
