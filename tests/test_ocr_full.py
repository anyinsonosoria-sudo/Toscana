#!/usr/bin/env python
"""
Test completo del sistema OCR
Simula la carga de una imagen y el procesamiento con OCR
"""

import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from app import app

# Crear imagen de prueba
print("=" * 70)
print("CREANDO IMAGEN DE PRUEBA...")
print("=" * 70)

# Crear una imagen simple con texto
img = Image.new('RGB', (300, 200), color='white')
draw = ImageDraw.Draw(img)

# Agregar texto simulando un recibo
text = "RECIBO\nMonto: $150.00\nFecha: 2026-01-09\nSuplidor: Test Store"
draw.text((10, 10), text, fill='black')

# Guardar en memoria
img_bytes = BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# Probar ruta de carga OCR
print("\nProbando ruta POST /gastos/upload-recibo...")
print("-" * 70)

with app.test_client() as client:
    # Enviar imagen como si fuera un formulario file upload
    response = client.post(
        '/gastos/upload-recibo',
        data={'file': (img_bytes, 'test_receipt.png')},
        content_type='multipart/form-data'
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Type: {response.content_type}")
    
    if response.status_code == 200:
        data = response.get_json()
        print(f"\n✓ RESPUESTA EXITOSA")
        print(f"  - Success: {data.get('success')}")
        print(f"  - Description: {data.get('description')}")
        print(f"  - Amount: {data.get('amount')}")
        print(f"  - Date: {data.get('date')}")
        print(f"  - Supplier: {data.get('supplier_name')}")
        print(f"  - Confidence: {data.get('confidence')}")
        print(f"  - Raw Text: {data.get('raw_text', 'N/A')[:100]}...")
    else:
        print(f"\n✗ ERROR EN LA RESPUESTA")
        print(f"Response: {response.get_json()}")

print("\n" + "=" * 70)
