"""
Script para probar la generación de recibos de pago con logo
"""
import receipt_pdf
import company
from pathlib import Path

# Obtener información de la empresa
company_info = company.get_company_info()

if not company_info:
    print("⚠️  No hay información de empresa configurada")
    exit(1)

print(f"✓ Información de empresa: {company_info['name']}")
if company_info.get('logo_path'):
    logo_path = Path(__file__).parent / 'static' / 'uploads' / company_info['logo_path']
    if logo_path.exists():
        print(f"✓ Logo encontrado: {company_info['logo_path']}")
    else:
        print(f"⚠️  Logo configurado pero archivo no existe")
else:
    print("ℹ️  No hay logo configurado")

# Datos de pago de prueba
payment_data = {
    'id': 555,
    'amount': 5000.00,
    'method': 'transferencia',
    'payment_date': 'January 09, 2026'
}

# Datos de factura relacionada
invoice_data = {
    'id': 123,
    'description': 'Mantenimiento Mensual - Enero 2026',
    'amount': 5000.00,
    'total_paid': 5000.00,
    'apartment_number': 'A-101',
    'resident_name': 'Juan Pérez',
    'resident_email': 'juan.perez@email.com',
    'resident_phone': '809-123-4567'
}

# Generar PDF de prueba
output_dir = Path(__file__).parent / "static" / "invoices"
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "test_payment_receipt.pdf"

print("\n" + "=" * 60)
print("GENERANDO RECIBO DE PAGO CON LOGO")
print("=" * 60)

try:
    receipt_pdf.generate_payment_receipt_pdf(payment_data, invoice_data, company_info, str(output_path))
    print(f"\n✓ Recibo generado exitosamente:")
    print(f"  📄 {output_path}")
    print(f"\n✓ Características:")
    print(f"  - Formato de moneda: RD$ 5,000.00")
    print(f"  - Logo en encabezado: {'SÍ' if company_info.get('logo_path') else 'NO'}")
    print(f"  - Logo en pie de página: {'SÍ' if company_info.get('logo_path') else 'NO'}")
    print(f"  - Estado de factura: PAGADA EN SU TOTALIDAD")
    print(f"\nℹ️  Abre el archivo para verificar el diseño")
except Exception as e:
    print(f"\n✗ Error al generar recibo: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)

# Prueba con pago parcial
print("\n" + "=" * 60)
print("GENERANDO RECIBO DE PAGO PARCIAL")
print("=" * 60)

payment_data_partial = {
    'id': 556,
    'amount': 2500.00,
    'method': 'efectivo',
    'payment_date': 'January 09, 2026'
}

invoice_data_partial = {
    'id': 124,
    'description': 'Mantenimiento Mensual - Enero 2026',
    'amount': 5000.00,
    'total_paid': 2500.00,
    'apartment_number': 'B-202',
    'resident_name': 'María González',
    'resident_email': 'maria.gonzalez@email.com',
    'resident_phone': '809-987-6543'
}

output_path_partial = output_dir / "test_payment_receipt_partial.pdf"

try:
    receipt_pdf.generate_payment_receipt_pdf(payment_data_partial, invoice_data_partial, company_info, str(output_path_partial))
    print(f"\n✓ Recibo de pago parcial generado exitosamente:")
    print(f"  📄 {output_path_partial}")
    print(f"\n✓ Características:")
    print(f"  - Monto pagado: RD$ 2,500.00")
    print(f"  - Saldo pendiente: RD$ 2,500.00")
    print(f"  - Método: Efectivo")
    print(f"\nℹ️  Abre el archivo para verificar el diseño")
except Exception as e:
    print(f"\n✗ Error al generar recibo parcial: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
