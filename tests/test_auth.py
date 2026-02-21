"""
Tests para el blueprint de autenticación
"""

import pytest


@pytest.mark.unit
def test_login_page_loads(client):
    """Test que la página de login carga correctamente"""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'Building Maintenance' in response.data


@pytest.mark.unit
def test_login_redirect_when_authenticated(auth_client):
    """Test que usuarios autenticados son redirigidos"""
    response = auth_client.get('/auth/login', follow_redirects=True)
    assert response.status_code == 200


@pytest.mark.unit
def test_logout(auth_client):
    """Test que logout funciona correctamente"""
    response = auth_client.get('/auth/logout', follow_redirects=True)
    assert response.status_code == 200


@pytest.mark.unit
def test_login_required_redirects(client):
    """Test que rutas protegidas redirigen a login"""
    routes = [
        '/apartamentos/',
        '/gastos/',
        '/productos/',
        '/facturacion',
        '/reportes/',
        '/contabilidad/',
        '/empresa/'
    ]
    
    for route in routes:
        response = client.get(route)
        assert response.status_code == 302  # Redirect
        assert '/auth/login' in response.location
