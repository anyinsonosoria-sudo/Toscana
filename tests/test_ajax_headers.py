#!/usr/bin/env python
"""Test OCR endpoint without AJAX headers

This script is runnable standalone but should not execute during pytest import.
Guard execution under `if __name__ == '__main__'` so pytest can import the module.
"""

import requests
from bs4 import BeautifulSoup
import io
from PIL import Image


if __name__ == '__main__':
    # Crear sesión
    session = requests.Session()

    # GET a /login y login
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

    print("[1] Usuario autenticado y sesión activa")

    # Crear imagen
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    # Prueba 1: SIN AJAX headers
    print("\n[2] Test 1: POST SIN AJAX headers...")
    files = {'file': ('test.png', img_bytes, 'image/png')}
    resp1 = session.post('http://localhost:5000/expenses/upload-recibo',
                        files=files,
                        allow_redirects=False)

    print(f"    Status: {resp1.status_code}")
    print(f"    Location: {resp1.headers.get('Location', 'None')}")
    print(f"    Response: {resp1.text[:200]}")

    # Prueba 2: CON AJAX header X-Requested-With
    print("\n[3] Test 2: POST CON AJAX header...")
    img_bytes.seek(0)
    files = {'file': ('test.png', img_bytes, 'image/png')}
    headers = {'X-Requested-With': 'XMLHttpRequest'}
    resp2 = session.post('http://localhost:5000/expenses/upload-recibo',
                        files=files,
                        headers=headers,
                        allow_redirects=False)

    print(f"    Status: {resp2.status_code}")
    print(f"    Location: {resp2.headers.get('Location', 'None')}")
    print(f"    Response: {resp2.text[:200]}")

    # Prueba 3: CON Content-Type application/json (aunque no es lo correcto para file upload)
    print("\n[4] Test 3: POST con application/json...")
    img_bytes.seek(0)
    resp3 = session.post('http://localhost:5000/expenses/upload-recibo',
                        files=files,
                        headers={'Accept': 'application/json'},
                        allow_redirects=False)

    print(f"    Status: {resp3.status_code}")
    print(f"    Response: {resp3.text[:200]}")
