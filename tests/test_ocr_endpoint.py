#!/usr/bin/env python
"""Test OCR endpoint to debug the issue"""

import requests
import sys
import io
from PIL import Image

# Crear sesión con cookies
session = requests.Session()

# Primero, hacer login
print("[1] Intentando login...")
login_data = {'username': 'admin', 'password': 'admin123'}
login_resp = session.post('http://localhost:5000/login', data=login_data, allow_redirects=True)
print(f"    Status: {login_resp.status_code}")

# Crear una imagen de prueba
print("\n[2] Creando imagen de prueba...")
img = Image.new('RGB', (100, 100), color='red')
img_bytes = io.BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# Ahora hacer test del endpoint OCR con archivo
print("\n[3] Enviando archivo OCR...")
headers = {'X-Requested-With': 'XMLHttpRequest'}
files = {'file': ('test.png', img_bytes, 'image/png')}
ocr_resp = session.post('http://localhost:5000/expenses/upload-recibo', 
                        files=files,
                        headers=headers)

print(f"    Status Code: {ocr_resp.status_code}")
print(f"    Content-Type: {ocr_resp.headers.get('Content-Type')}")
print(f"    Response (primeros 1000 chars):\n{ocr_resp.text[:1000]}")

# Verificar si es JSON válido
try:
    json_data = ocr_resp.json()
    print("\n[4] ✓ La respuesta es JSON válido")
    print(f"    Keys: {list(json_data.keys())}")
except Exception as e:
    print(f"\n[4] ✗ Error parseando JSON: {e}")
    if '<' in ocr_resp.text[:10]:
        print("    → La respuesta parece ser HTML (empieza con '<')")
