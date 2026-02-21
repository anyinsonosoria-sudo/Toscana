#!/usr/bin/env python
"""Test improved OCR with realistic receipt image"""

import requests
from bs4 import BeautifulSoup
import io
from PIL import Image, ImageDraw, ImageFont

# Crear sesión
session = requests.Session()

# Login
print("[1] Autenticando...")
login_page = session.get('http://localhost:5000/auth/login')
soup = BeautifulSoup(login_page.text, 'html.parser')
csrf_token = soup.find('input', {'name': 'csrf_token'})['value']

session.post('http://localhost:5000/auth/login', 
            data={
                'username': 'admin',
                'password': 'admin123',
                'csrf_token': csrf_token
            },
            allow_redirects=True)

print("    ✓ Usuario autenticado")

# Crear imagen realista de recibo
print("\n[2] Creando imagen de recibo realista...")
img = Image.new('RGB', (400, 300), color='white')
draw = ImageDraw.Draw(img)

# Simular un recibo
receipt_text = """
================================
    SUPERMERCADO ABC
        RNC: 12345678
================================

FECHA: 15/01/2025
HORA: 10:30 AM
Cajero: Juan

--------------------------------
PRODUCTOS:
Leche 1L           $2.50
Pan Integral       $1.25
Pollo (kg)        $5.99
Arroz 2kg         $3.75
Café molido       $4.50

--------------------------------
SUBTOTAL:         $18.99
ITBIS (18%):      $3.42
TOTAL:            $22.41

Muchas gracias por su compra!
"""

y = 10
for line in receipt_text.split('\n'):
    draw.text((5, y), line, fill='black')
    y += 15

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
    print(f"\n✓ OCR PROCESADO - Status: {json_data.get('success')}")
    
    if json_data.get('success'):
        print(f"\n📊 CAMPOS EXTRAÍDOS:")
        print(f"  ✓ Proveedor: {json_data.get('supplier_name', 'N/A')}")
        print(f"  ✓ Monto: ${json_data.get('amount', 'N/A')}")
        print(f"  ✓ Fecha: {json_data.get('date', 'N/A')}")
        print(f"  ✓ Descripción: {json_data.get('description', 'N/A')[:80]}...")
        print(f"  ✓ Confianza: {json_data.get('confidence', 0)*100:.0f}%")
        print(f"\n📝 TEXTO EXTRAÍDO (primeras 300 chars):")
        print(f"  {json_data.get('raw_text', 'N/A')[:300]}...")
    else:
        print(f"  ✗ Error: {json_data.get('error')}")
        
except Exception as e:
    print(f"\n✗ Error: {type(e).__name__}: {e}")
    print(f"Response: {resp.text[:500]}")
