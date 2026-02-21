#!/usr/bin/env python
"""
Verificar que el OCR modal está correctamente configurado
"""

from app import app

with app.test_client() as client:
    response = client.get('/gastos')
    content = response.data.decode()
    
    print("=" * 70)
    print("VERIFICACIÓN DE MODAL OCR EN PÁGINA")
    print("=" * 70)
    
    checks = {
        'Modal OCR existe': 'id="ocrReceiptModal"' in content,
        'Botón "Cargar Recibo (OCR)"': 'Cargar Recibo (OCR)' in content,
        'Input file': 'id="receiptFileInput"' in content,
        'Form OCR': 'id="ocrReceiptForm"' in content,
        'Ruta /gastos/upload-recibo': '/gastos/upload-recibo' in content,
        'JavaScript btnProcessOcr': 'btnProcessOcr' in content,
        'JavaScript receiptFileInput': 'receiptFileInput' in content,
    }
    
    all_ok = True
    for check, result in checks.items():
        status = "✓" if result else "✗"
        print(f"{status} {check}")
        if not result:
            all_ok = False
    
    print("\n" + "=" * 70)
    if all_ok:
        print("✓ TODO ESTÁ CONFIGURADO CORRECTAMENTE")
    else:
        print("✗ Hay problemas en la configuración")
    print("=" * 70)
