"""
Tests para el blueprint de autenticación
"""

import pytest

import apartments
import residents
import user_model


@pytest.mark.unit
def test_login_page_loads(client):
    """Test que la página de login carga correctamente"""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'Residencial Toscana' in response.data or b'Toscana' in response.data


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
        '/ventas/facturas',
        '/reportes/',
        '/contabilidad/',
        '/empresa/'
    ]
    
    for route in routes:
        response = client.get(route)
        assert response.status_code == 302  # Redirect
        assert '/auth/login' in response.location


@pytest.mark.integration
def test_register_form_exposes_resident_link_status(auth_client):
    response = auth_client.get('/auth/register')

    assert response.status_code == 200
    assert b'resident_link_status' in response.data
    assert b'Invitado con c' in response.data


@pytest.mark.integration
def test_register_resident_invitation_redirects_to_edit_with_visible_code(auth_client, app):
    with app.app_context():
        unit_id = apartments.add_apartment(number='UI-101', resident_name='UI Resident', resident_email='')

    response = auth_client.post(
        '/auth/register',
        data={
            'username': 'ui_invited_resident',
            'email': 'ui_invited@example.com',
            'password': 'password123',
            'password_confirm': 'password123',
            'full_name': 'UI Invited Resident',
            'role': 'resident',
            'apartment_id': str(unit_id),
            'resident_link_status': 'invited',
        },
        follow_redirects=False,
    )

    with app.app_context():
        user = user_model.get_user_by_username('ui_invited_resident')
        invitation = residents.list_pending_invitations_for_user(user.id)[0]

    assert response.status_code == 302
    assert f'/auth/users/{user.id}/edit' in response.location

    page = auth_client.get(response.location)

    assert page.status_code == 200
    assert b'Codigo de invitacion activo' in page.data
    assert invitation['invitation_code'].encode() in page.data
