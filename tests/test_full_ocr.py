#!/usr/bin/env python
"""Test OCR endpoint - complete version with all headers"""

import requests
from bs4 import BeautifulSoup
import io
from PIL import Image

# Crear sesión
session = requests.Session()

# GET a /login
print("[1] Obteniendo formulario de login...")
login_page = session.get('http://localhost:5000/auth/login')
soup = BeautifulSoup(login_page.text, 'html.parser')
csrf_token = soup.find('input', {'name': 'csrf_token'})['value']
print(f"    CSRF token: {csrf_token[:30]}...")

# POST al login
print("\n[2] Haciendo login...")
login_resp = session.post('http://localhost:5000/auth/login', 
                         data={
                             'username': 'admin',
                             'password': 'admin123',
                             'csrf_token': csrf_token
                         },
                         allow_redirects=True)

print(f"    URL final: {login_resp.url}")
print(f"    Usuario autenticado: {'Bienvenido' in login_resp.text}")

# Ahora hacer el OCR con archivo
print("\n[3] Creando imagen de prueba...")
img = Image.new('RGB', (100, 100), color='red')
img_bytes = io.BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

print("\n[4] Enviando archivo OCR a /expenses/upload-recibo...")
headers = {
    'X-Requested-With': 'XMLHttpRequest'
}
files = {
    'file': ('test.png', img_bytes, 'image/png')
}

ocr_resp = session.post('http://localhost:5000/expenses/upload-recibo',
                       files=files,
                       headers=headers,
                       allow_redirects=False)

print(f"    Status Code: {ocr_resp.status_code}")
print(f"    Content-Type: {ocr_resp.headers.get('Content-Type')}")

if ocr_resp.status_code == 302:
    print(f"    Redirect Location: {ocr_resp.headers.get('Location')}")
    print(f"    Response: {ocr_resp.text[:200]}")
else:
    print(f"    Response (primeros 500 chars):\n{ocr_resp.text[:500]}")

try:
    json_data = ocr_resp.json()
    print(f"\n✓ JSON válido!")
    print(f"  Success: {json_data.get('success')}")
    if json_data.get('error'):
        print(f"  Error: {json_data.get('error')}")
    elif json_data.get('message'):
        print(f"  Message: {json_data.get('message')}")
except Exception as e:
    print(f"\n✗ Error parseando JSON: {type(e).__name__}")
