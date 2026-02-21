#!/usr/bin/env python
"""Test OCR endpoint - follow redirects on login"""

import requests
from bs4 import BeautifulSoup

# Crear sesión
session = requests.Session()

# GET a /login
login_page = session.get('http://localhost:5000/auth/login')
soup = BeautifulSoup(login_page.text, 'html.parser')
csrf_token = soup.find('input', {'name': 'csrf_token'})['value']

print(f"[1] CSRF token: {csrf_token[:20]}...")

# POST al login (SIN allow_redirects=False, para seguir redirs)
login_resp = session.post('http://localhost:5000/auth/login', 
                         data={
                             'username': 'admin',
                             'password': 'admin123',
                             'csrf_token': csrf_token
                         },
                         allow_redirects=True)

print(f"[2] Login Status: {login_resp.status_code}")
print(f"[3] Login URL final: {login_resp.url}")
print(f"[4] ¿Contiene 'Bienvenido'?: {'Bienvenido' in login_resp.text}")

# Probar endpoint /expenses (sin OCR, solo para verificar auth)
expenses_resp = session.get('http://localhost:5000/expenses', 
                           headers={'X-Requested-With': 'XMLHttpRequest'})
print(f"\n[5] GET /expenses Status: {expenses_resp.status_code}")
print(f"[6] GET /expenses Response (primeros 200 chars): {expenses_resp.text[:200]}")

# Ahora probar el OCR sin archivo (solo para ver si entiende AJAX)
ocr_resp = session.post('http://localhost:5000/expenses/upload-recibo',
                       headers={'X-Requested-With': 'XMLHttpRequest'},
                       allow_redirects=False)

print(f"\n[7] POST /expenses/upload-recibo Status: {ocr_resp.status_code}")
print(f"[8] Content-Type: {ocr_resp.headers.get('Content-Type')}")
print(f"[9] Response (primeros 300 chars): {ocr_resp.text[:300]}")

try:
    json_data = ocr_resp.json()
    print(f"\n✓ JSON válido! Keys: {list(json_data.keys())}")
except:
    print(f"\n✗ No es JSON")
