"""
Script para configurar un logo de prueba en la empresa
"""
import company

# Obtener información actual
current_info = company.get_company_info()

if current_info:
    print(f"✓ Empresa actual: {current_info['name']}")
    # Actualizar con el logo
    company.update_company_info(
        name=current_info['name'],
        legal_id=current_info.get('legal_id'),
        address=current_info.get('address'),
        city=current_info.get('city'),
        country=current_info.get('country'),
        phone=current_info.get('phone'),
        email=current_info.get('email'),
        website=current_info.get('website'),
        bank_name=current_info.get('bank_name'),
        bank_account=current_info.get('bank_account'),
        bank_routing=current_info.get('bank_routing'),
        tax_id=current_info.get('tax_id'),
        logo_path='Toscana.png',  # Usar logo existente
        notes=current_info.get('notes')
    )
    print("✓ Logo actualizado: Toscana.png")
else:
    print("⚠️  No hay información de empresa. Creando...")
    company.update_company_info(
        name='Residencial Toscana',
        address='Av. Principal 123',
        city='Santo Domingo',
        country='República Dominicana',
        phone='809-555-1234',
        email='admin@toscana.com',
        bank_account='1234567890',
        logo_path='Toscana.png'
    )
    print("✓ Empresa creada con logo: Toscana.png")

# Verificar
updated_info = company.get_company_info()
print(f"\n✓ Logo configurado: {updated_info.get('logo_path')}")
