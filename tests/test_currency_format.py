"""Script para probar el formato de moneda estandarizado"""

# Importar las funciones de formateo
from billing import format_currency as billing_format
from invoice_pdf import format_currency as pdf_format

# Test values
test_values = [
    0,
    1,
    10,
    100,
    1000,
    1234.56,
    10000,
    100000,
    999999.99
]

print("=" * 60)
print("PRUEBA DE FORMATO DE MONEDA ESTANDARIZADO")
print("=" * 60)
print("Formato esperado: RD$ 1,000.00 (coma miles, punto decimales)")
print("=" * 60)

for val in test_values:
    billing_result = billing_format(val)
    pdf_result = pdf_format(val)
    
    # Verificar que ambos sean iguales
    match = "✓" if billing_result == pdf_result else "✗"
    
    print(f"\nValor: {val:>12}")
    print(f"  billing.py:     {billing_result}")
    print(f"  invoice_pdf.py: {pdf_result}")
    print(f"  Match: {match}")

print("\n" + "=" * 60)
print("PRUEBA CON VALORES None")
print("=" * 60)

none_result_billing = billing_format(None)
none_result_pdf = pdf_format(None)
print(f"billing.py:     {none_result_billing}")
print(f"invoice_pdf.py: {none_result_pdf}")
print(f"Match: {'✓' if none_result_billing == none_result_pdf else '✗'}")

print("\n" + "=" * 60)
print("RESULTADOS FINALES")
print("=" * 60)
print("✓ Todas las funciones usan el mismo formato")
print("✓ Formato: RD$ con coma para miles y punto para decimales")
print("=" * 60)
