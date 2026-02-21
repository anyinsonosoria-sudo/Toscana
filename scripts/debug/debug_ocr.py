#!/usr/bin/env python
"""Debug OCR text extraction"""

import io
from PIL import Image, ImageDraw
from ocr_processing import ReceiptOCR

# Crear imagen de prueba
img = Image.new('RGB', (500, 400), color='white')
draw = ImageDraw.Draw(img)

receipt_text = """
=================================
    TIENDA LOS AMIGOS
         RNC: 123456789
=================================

FECHA: 16 DE ENERO DEL 2025

ARTICULOS VENDIDOS:
1. Arroz                10.50
2. Frijoles             8.75
3. Aceite              12.99
4. Leche                 3.50
5. Pan                   2.25
6. Pollo por kg         15.00

------- RESUMEN ----------
SUBTOTAL:              52.99
DESCUENTO:             0.00
ITBIS 18%:             9.54
------- TOTAL ----------
TOTAL A PAGAR:         62.53

Gracias por su compra
"""

y = 10
for line in receipt_text.split('\n'):
    draw.text((10, y), line, fill='black')
    y += 18

# Convertir imagen a bytes
img_bytes = io.BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# Procesar con OCR
print("[1] Procesando imagen con OCR...")
result = ReceiptOCR.process_image_bytes(img_bytes.getvalue())

print(f"\n[2] TEXTO EXTRAÍDO:")
print(result['raw_text'])

print(f"\n[3] CAMPOS DETECTADOS:")
print(f"  Monto: {result.get('amount')}")
print(f"  Fecha: {result.get('date')}")
print(f"  Proveedor: {result.get('supplier_name')}")
print(f"  Confianza: {result.get('confidence')}")
