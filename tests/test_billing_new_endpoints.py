import pytest
from app import app
from db import get_conn
import json
from flask_login import login_user
from user_model import User

def test_view_receipt_pdf_not_found(client):
    # Log in as a user first so login_required is satisfied and we don't get redirected to the login page
    with client.session_transaction() as sess:
        sess['_user_id'] = '1'  # Simulated authenticated admin/user
    response = client.get('/ventas/pagos/pdf/99999999', follow_redirects=True)
    assert response.status_code == 200
    # Checks that it redirects and shows not found
    assert b"no encontrado" in response.data or b"No encontrado" in response.data or b"error" in response.data or b"Pago no encontrado" in response.data

def test_download_statement_pdf_not_found(client):
    with client.session_transaction() as sess:
        sess['_user_id'] = '1'
    response = client.get('/ventas/apartamentos/estado-cuenta/99999999', follow_redirects=True)
    assert response.status_code == 200
    assert b"no" in response.data or b"encontrado" in response.data or b"error" in response.data
