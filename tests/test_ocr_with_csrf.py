#!/usr/bin/env python
"""Test OCR endpoint with CSRF token handling"""

import requests
from bs4 import BeautifulSoup
import sys
import io
from PIL import Image

# Crear sesión con cookies
session = requests.Session()

# Primero, hacer GET a /login para obtener el CSRF token
print("[1] Obteniendo CSRF token...")
login_page = session.get('http://localhost:5000/auth/login')
soup = BeautifulSoup(login_page.text, 'html.parser')
csrf_token = soup.find('input', {'name': 'csrf_token'})

if csrf_token:
    csrf_value = csrf_token['value']
    print(f"    ✓ CSRF token obtenido: {csrf_value[:20]}...")
else:
    print("    ✗ No se encontró CSRF token en el formulario")
    sys.exit(1)

# Ahora hacer POST al login con el CSRF token
print("\n[2] Intentando login con CSRF token...")
login_data = {
    'username': 'admin',
    'password': 'admin123',
    'csrf_token': csrf_value
}
login_resp = session.post('http://localhost:5000/auth/login', 
                         data=login_data, 
                         allow_redirects=False)  # No seguir redirects
print(f"    Status: {login_resp.status_code}")
print(f"    Location: {login_resp.headers.get('Location', 'None')}")
print(f"    Contiene 'Bienvenido': {'Bienvenido' in login_resp.text}")
print(f"    Cookies: {list(session.cookies.keys())}")

# Crear una imagen de prueba
print("\n[3] Creando imagen de prueba...")
img = Image.new('RGB', (100, 100), color='red')
img_bytes = io.BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# Ahora hacer test del endpoint OCR con archivo
print("\n[4] Enviando archivo OCR...")
print(f"    Cookies antes de OCR: {list(session.cookies.keys())}")
headers = {'X-Requested-With': 'XMLHttpRequest'}
files = {'file': ('test.png', img_bytes, 'image/png')}
ocr_resp = session.post('http://localhost:5000/expenses/upload-recibo', 
                        files=files,
                        headers=headers,
                        allow_redirects=False)

print(f"    Status Code: {ocr_resp.status_code}")
print(f"    Content-Type: {ocr_resp.headers.get('Content-Type')}")
print(f"    Response (primeros 500 chars):\n{ocr_resp.text[:500]}")

# Verificar si es JSON válido
try:
    json_data = ocr_resp.json()
    print("\n[5] ✓ La respuesta es JSON válido!")
    print(f"    Success: {json_data.get('success')}")
    if json_data.get('error'):
        print(f"    Error: {json_data.get('error')}")
    if json_data.get('message'):
        print(f"    Message: {json_data.get('message')}")
except Exception as e:
    print(f"\n[5] ✗ Error parseando JSON: {e}")
    if '<' in ocr_resp.text[:10]:
        print("    → La respuesta es HTML, no JSON")
