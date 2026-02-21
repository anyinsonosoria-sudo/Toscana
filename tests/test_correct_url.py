#!/usr/bin/env python
"""Test OCR endpoint with CORRECT URL"""

import requests
from bs4 import BeautifulSoup
import io
from PIL import Image

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

# Crear imagen
img = Image.new('RGB', (100, 100), color='red')
img_bytes = io.BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# TEST CORRECTO: /gastos/upload-recibo
print("\n[2] Enviando archivo a /gastos/upload-recibo...")
files = {'file': ('test.png', img_bytes, 'image/png')}
headers = {'X-Requested-With': 'XMLHttpRequest'}
resp = session.post('http://localhost:5000/gastos/upload-recibo',
                   files=files,
                   headers=headers,
                   allow_redirects=False)

print(f"    Status: {resp.status_code}")
print(f"    Content-Type: {resp.headers.get('Content-Type')}")

if resp.status_code != 200:
    print(f"    Redirect: {resp.headers.get('Location', 'None')}")
    print(f"    Response (primeros 200 chars): {resp.text[:200]}")
else:
    print(f"    Response (primeros 500 chars): {resp.text[:500]}")

try:
    json_data = resp.json()
    print(f"\n✓ JSON VÁLIDO!")
    print(f"  Success: {json_data.get('success')}")
    if json_data.get('error'):
        print(f"  Error: {json_data.get('error')}")
    elif json_data.get('message'):
        print(f"  Message: {json_data.get('message')}")
    else:
        print(f"  Keys: {list(json_data.keys())}")
except Exception as e:
    print(f"\n✗ Error parseando JSON: {type(e).__name__}: {e}")
