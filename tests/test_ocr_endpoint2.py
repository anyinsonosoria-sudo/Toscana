#!/usr/bin/env python
"""Test OCR endpoint with better session handling"""

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
print(f"    URL final: {login_resp.url}")
print(f"    Cookies en session: {session.cookies.get_dict()}")
print(f"    Contiene 'Bienvenido': {'Bienvenido' in login_resp.text}")

# Crear una imagen de prueba
print("\n[2] Creando imagen de prueba...")
img = Image.new('RGB', (100, 100), color='red')
img_bytes = io.BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# Ahora hacer test del endpoint OCR con archivo
print("\n[3] Enviando archivo OCR...")
print(f"    Cookies antes de OCR: {session.cookies.get_dict()}")
headers = {'X-Requested-With': 'XMLHttpRequest'}
files = {'file': ('test.png', img_bytes, 'image/png')}
ocr_resp = session.post('http://localhost:5000/expenses/upload-recibo', 
                        files=files,
                        headers=headers,
                        allow_redirects=False)  # No seguir redirects para ver qué pasa

print(f"    Status Code: {ocr_resp.status_code}")
print(f"    Content-Type: {ocr_resp.headers.get('Content-Type')}")
print(f"    Redirect Location: {ocr_resp.headers.get('Location', 'None')}")
print(f"    Response (primeros 500 chars):\n{ocr_resp.text[:500]}")

# Verificar si es JSON válido
try:
    json_data = ocr_resp.json()
    print("\n[4] ✓ La respuesta es JSON válido")
    print(f"    Keys: {list(json_data.keys())}")
except Exception as e:
    print(f"\n[4] ✗ Error parseando JSON: {e}")
