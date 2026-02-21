#!/usr/bin/env python
"""Test OCR with very clear decimal formatting"""

import requests
from bs4 import BeautifulSoup
import io
from PIL import Image, ImageDraw, ImageFont

session = requests.Session()

# Login
print("[1] Autenticando...")
login_page = session.get('http://localhost:5000/auth/login')
soup = BeautifulSoup(login_page.text, 'html.parser')
csrf_token = soup.find('input', {'name': 'csrf_token'})['value']

session.post('http://localhost:5000/auth/login', 
            data={'username': 'admin', 'password': 'admin123', 'csrf_token': csrf_token},
            allow_redirects=True)

print("    ✓ Usuario autenticado")

# Crear imagen con formato MUY claro
print("\n[2] Creando recibo con decimales bien visibles...")
img = Image.new('RGB', (500, 400), color='white')
draw = ImageDraw.Draw(img)

# Recibo con decimales claramente separados
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

img_bytes = io.BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# Test OCR
print("\n[3] Enviando imagen a OCR...")
files = {'file': ('receipt.png', img_bytes, 'image/png')}
headers = {'X-Requested-With': 'XMLHttpRequest'}
resp = session.post('http://localhost:5000/gastos/upload-recibo',
                   files=files,
                   headers=headers,
                   allow_redirects=False)

print(f"    Status: {resp.status_code}")

try:
    json_data = resp.json()
    if json_data.get('success'):
        print(f"\n✓ OCR EXITOSO")
        print(f"\n📊 CAMPOS EXTRAÍDOS:")
        print(f"  • Proveedor: {json_data.get('supplier_name', 'N/A')}")
        print(f"  • Monto: ${json_data.get('amount', 'NO DETECTADO')}")
        print(f"  • Fecha: {json_data.get('date', 'N/A')}")
        print(f"  • Descripción: {json_data.get('description', 'N/A')[:60]}...")
        print(f"  • Confianza: {json_data.get('confidence', 0)*100:.0f}%")
    else:
        print(f"✗ Error: {json_data.get('error')}")
        
except Exception as e:
    print(f"✗ Error: {e}")
