#!/usr/bin/env python
"""Test OCR endpoint with a REAL receipt image with text"""

import requests
from bs4 import BeautifulSoup
import io
from PIL import Image, ImageDraw, ImageFont

# Crear sesión
session = requests.Session()

# GET a /login y login
print("[1] Haciendo login...")
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

# Crear imagen CON TEXTO
print("\n[2] Creando imagen de recibo con texto...")
img = Image.new('RGB', (400, 200), color='white')
draw = ImageDraw.Draw(img)

# Escribir texto simulando un recibo
text_lines = [
    "STORE RECEIPT",
    "Product 1: $10.50",
    "Product 2: $5.99",
    "Subtotal: $16.49",
    "Tax: $1.31",
    "Total: $17.80"
]

y = 10
for line in text_lines:
    draw.text((10, y), line, fill='black')
    y += 25

img_bytes = io.BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# TEST: /gastos/upload-recibo
print("\n[3] Enviando imagen con texto...")
files = {'file': ('receipt.png', img_bytes, 'image/png')}
headers = {'X-Requested-With': 'XMLHttpRequest'}
resp = session.post('http://localhost:5000/gastos/upload-recibo',
                   files=files,
                   headers=headers,
                   allow_redirects=False)

print(f"    Status: {resp.status_code}")
print(f"    Content-Type: {resp.headers.get('Content-Type')}")

try:
    json_data = resp.json()
    print(f"\n✓ JSON VÁLIDO! Status: {json_data.get('success')}")
    
    if json_data.get('success'):
        print(f"    ✓ OCR EXITOSO")
        print(f"    - Amount: ${json_data.get('amount', 'N/A')}")
        print(f"    - Confidence: {json_data.get('confidence', 'N/A')*100:.0f}%")
        print(f"    - Description: {json_data.get('description', 'N/A')}")
        print(f"    - Raw text: {json_data.get('raw_text', 'N/A')[:100]}...")
        print(f"    - Message: {json_data.get('message', 'N/A')}")
    else:
        print(f"    Error: {json_data.get('error')}")
        print(f"    Raw text: {json_data.get('raw_text', 'N/A')}")
        
except Exception as e:
    print(f"\n✗ Error: {type(e).__name__}: {e}")
    print(f"Response: {resp.text}")
