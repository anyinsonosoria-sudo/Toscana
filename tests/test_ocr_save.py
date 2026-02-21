#!/usr/bin/env python
"""
Test completo: Upload OCR + Guardar Gasto
"""

import io
from PIL import Image, ImageDraw
from app import app
from ocr_processing import ReceiptOCR
from datetime import datetime

print("=" * 70)
print("TEST COMPLETO: OCR + GUARDAR GASTO")
print("=" * 70)

# Crear imagen de prueba
img = Image.new('RGB', (600, 400), 'white')
draw = ImageDraw.Draw(img)
text = '''RECIBO
MONTO: 250.50
FECHA: 2026-01-09
SUPLIDOR: TEST STORE'''
draw.text((50, 50), text, fill='black')

# Guardar en memoria
png_bytes = io.BytesIO()
img.save(png_bytes, format='PNG')
png_bytes.seek(0)

# Durante tests, simular resultado OCR para no depender de tesseract local
ReceiptOCR.process_image_bytes = staticmethod(lambda b: {
    'description': 'RECIBO',
    'amount': 250.50,
    'date': '2026-01-09',
    'supplier_name': 'TEST STORE',
    'confidence': 0.95,
    'raw_text': 'RECIBO\nMONTO: 250.50\nFECHA: 2026-01-09',
    'error': None
})

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False

with app.test_client() as client:
    # Autenticar sesión como admin para pasar decoradores @login_required y permisos
    with client.session_transaction() as sess:
        # El id del admin por defecto creado en `db.init_db()` suele ser 1
        sess['_user_id'] = '1'
        sess['_fresh'] = True
    # PASO 1: Procesar OCR
    print("\n[1/2] Procesando OCR...")
    response = client.post(
        '/gastos/upload-recibo',
        data={'file': (png_bytes, 'test_receipt.png')},
        content_type='multipart/form-data'
    )
    
    if response.status_code == 200:
        ocr_data = response.get_json()
        print(f"✓ OCR exitoso (Status {response.status_code})")
        print(f"  - Monto: {ocr_data.get('amount')}")
        print(f"  - Fecha: {ocr_data.get('date')}")
        print(f"  - Descripción: {ocr_data.get('description')}")
        print(f"  - Confianza: {ocr_data.get('confidence')}")
    else:
        print(f"✗ OCR falló (Status {response.status_code})")
        print(f"  {response.get_json()}")
        exit(1)
    
    # PASO 2: Guardar gasto con recibo
    print("\n[2/2] Guardando gasto con recibo...")
    
    # Obtener la imagen base64 de la respuesta
    receipt_image_b64 = ocr_data.get('receipt_image_b64', '')
    
    save_response = client.post(
        '/gastos/save-with-receipt',
        data={
            'description': ocr_data.get('description', 'Gasto del recibo OCR'),
            'amount': ocr_data.get('amount', 0),
            'date': ocr_data.get('date', datetime.now().strftime('%Y-%m-%d')),
            'category': 'Otros',
            'supplier_id': '',
            'payment_method': 'Efectivo',
            'notes': f"OCR Confianza: {ocr_data.get('confidence', 0):.0%}",
            'receipt_image_b64': receipt_image_b64  # Enviar imagen base64
        }
    )
    
    print(f"✓ Respuesta guardado: Status {save_response.status_code}")
    
    if save_response.status_code == 302:  # Redirect = éxito
        print("✓ Gasto guardado correctamente (Redirect 302)")
    elif 'success' in str(save_response.data).lower():
        print("✓ Gasto guardado correctamente")
    else:
        print(f"⚠ Status: {save_response.status_code}")
        print(f"Respuesta: {save_response.data.decode()[:200]}")

print("\n" + "=" * 70)
print("✓ TEST COMPLETO FINALIZADO")
print("=" * 70)
