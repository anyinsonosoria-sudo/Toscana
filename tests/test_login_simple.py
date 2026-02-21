"""Test simple de login"""
import requests

session = requests.Session()

# 1. Get login page
print("1. Obteniendo pagina de login...")
response = session.get("http://localhost:5000/auth/login")
print(f"   Status: {response.status_code}")

# 2. Extract CSRF token
import re
match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.text)
csrf_token = match.group(1) if match else None
print(f"   CSRF token: {csrf_token[:20] if csrf_token else 'NO ENCONTRADO'}...")

# 3. Login
print("\n2. Intentando login...")
login_data = {
    'username': 'admin',
    'password': 'admin123',
    'csrf_token': csrf_token
}

response = session.post(
    "http://localhost:5000/auth/login",
    data=login_data,
    allow_redirects=False
)

print(f"   Status: {response.status_code}")
if response.status_code == 302:
    print(f"   Redirige a: {response.headers.get('Location')}")
    print("   ✅ LOGIN EXITOSO")
else:
    print(f"   ❌ LOGIN FALLO")
    print(f"   Response: {response.text[:200]}")
