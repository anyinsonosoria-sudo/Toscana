#!/usr/bin/env python3
"""Integration-style test for OCR endpoint using Flask test client.

This replaces the previous standalone script that required a running server
and instead uses the application's `create_app()` factory and test client.
"""
import io
from PIL import Image, ImageDraw
import base64

from app import create_app
from ocr_processing import ReceiptOCR


def make_test_image_bytes():
    img = Image.new('RGB', (400, 600), color='white')
    d = ImageDraw.Draw(img)
    lines = [
        'TIENDALOSAMIGOS',
        'RNC: 123456789',
        'FECHA: 16 DE ENERO DEL 2025',
        'ARTICULOS VENDIDOS:',
        'Leche 1L          2.50',
        'TOTAL A PAGAR:   62.53'
    ]
    y = 20
    for l in lines:
        d.text((20, y), l, fill='black')
        y += 25

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()


def test_upload_receipt_uses_test_client_and_returns_json():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    # Mock OCR to avoid dependency on local Tesseract
    ReceiptOCR.process_image_bytes = staticmethod(lambda b: {
        'description': 'TIENDA TEST',
        'amount': 62.53,
        'date': '2025-01-16',
        'supplier_name': 'TIENDALOSAMIGOS',
        'confidence': 0.9,
        'raw_text': '...mocked...',
        'error': None
    })

    img_bytes = make_test_image_bytes()

    with app.test_client() as client:
        # Set a logged-in user in the session to bypass @login_required
        with client.session_transaction() as sess:
            sess['_user_id'] = '1'
            sess['_fresh'] = True

        data = {
            'file': (io.BytesIO(img_bytes), 'receipt.png')
        }

        resp = client.post('/gastos/upload-recibo', data=data, content_type='multipart/form-data')

        assert resp.status_code == 200, f"Unexpected status: {resp.status_code} - {resp.data}"
        json_data = resp.get_json()
        assert json_data and json_data.get('success') is True
        assert abs(float(json_data.get('amount', 0)) - 62.53) < 0.01
#!/usr/bin/env python3
"""Test OCR endpoint with current implementation"""
import requests
import json
from PIL import Image, ImageDraw
import io
import time
import sys

# Wait for server
time.sleep(2)

# Create test image
img = Image.new('RGB', (400, 600), color='white')
d = ImageDraw.Draw(img)

text_lines = [
    'TIENDALOSAMIGOS',
    'RNC: 123456789',
    '',
    'FECHA: 16 DE ENERO DEL 2025',
    '',
    'ARTICULOS VENDIDOS:',
    'Leche 1L          2.50',
    'Frijoles          8.75',
    'Aceite           12.99',
    'Pan               3.50',
    'Pollo por kg     15.00',
    '',
    'SUBTOTAL:        52.99',
    'DESCUENTO:        0.00',
    'IMPUESTO (18%):   9.54',
    '',
    'TOTAL A PAGAR:   62.53'
]

y_pos = 20
for line in text_lines:
    d.text((20, y_pos), line, fill='black')
    y_pos += 25

img_bytes = io.BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

url = 'http://localhost:5000/gastos/upload-recibo'
files = {'file': ('receipt.png', img_bytes, 'image/png')}

try:
    response = requests.post(url, files=files, timeout=10)
    print(f'Status: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f'Response: {response.text}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
    sys.exit(1)
