from pathlib import Path

import pytest

import apartments
import db
import receipt_pdf
import residents
import user_model


def _reset_api_state():
    conn = db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM resident_api_refresh_tokens")
        cur.execute("DELETE FROM resident_user_units")
        cur.execute("DELETE FROM payments")
        cur.execute("DELETE FROM invoices")
        cur.execute("DELETE FROM residents")
        cur.execute("DELETE FROM apartments")
        cur.execute("DELETE FROM users WHERE username != 'admin'")
        conn.commit()
    finally:
        conn.close()


def _login_user_session(client, user_id: int):
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


def _authorization_headers(access_token: str):
    return {'Authorization': f'Bearer {access_token}'}


@pytest.mark.integration
def test_resident_api_returns_profile_apartments_invoices_and_summary(client, app):
    with app.app_context():
        _reset_api_state()
        unit_id = apartments.add_apartment(number='M-101', resident_name='Mobile Resident', resident_email='')
        user_id = user_model.create_user(
            username='mobile_resident',
            email='mobile_resident@example.com',
            password='password123',
            full_name='Mobile Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='mobile_resident@example.com',
            resident_name='Mobile Resident',
            created_by=1,
        )

        conn = db.get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO invoices (unit_id, description, amount, issued_date, due_date, paid) VALUES (?, ?, ?, ?, ?, ?)",
                (unit_id, 'Cuota ordinaria', 150.0, '2026-05-01', '2026-05-15', 0),
            )
            invoice_id = cur.lastrowid
            cur.execute(
                "INSERT INTO payments (invoice_id, amount, paid_date, method, notes) VALUES (?, ?, ?, ?, ?)",
                (invoice_id, 50.0, '2026-05-10', 'transfer', 'Pago parcial'),
            )
            conn.commit()
        finally:
            conn.close()

    _login_user_session(client, user_id)

    profile_response = client.get('/api/resident/profile')
    apartments_response = client.get('/api/resident/apartments')
    invoices_response = client.get('/api/resident/invoices')
    summary_response = client.get('/api/resident/statement-summary')

    assert profile_response.status_code == 200
    assert apartments_response.status_code == 200
    assert invoices_response.status_code == 200
    assert summary_response.status_code == 200

    profile_payload = profile_response.get_json()
    apartments_payload = apartments_response.get_json()
    invoices_payload = invoices_response.get_json()
    summary_payload = summary_response.get_json()

    assert profile_payload['profile']['email'] == 'mobile_resident@example.com'
    assert profile_payload['totals']['balance'] == 100.0
    assert len(apartments_payload['apartments']) == 1
    assert apartments_payload['apartments'][0]['number'] == 'M-101'
    assert invoices_payload['invoices'][0]['remaining'] == 100.0
    assert invoices_payload['invoices'][0]['pdf_url'].endswith(f"/api/resident/invoices/{invoice_id}/pdf")
    assert summary_payload['summary']['totals']['balance'] == 100.0
    assert summary_payload['summary']['apartments'][0]['statement_pdf_url'].endswith(
        f"/api/resident/apartments/{unit_id}/statement.pdf"
    )


@pytest.mark.integration
def test_resident_api_activates_invitation_code(client, app):
    with app.app_context():
        _reset_api_state()
        unit_id = apartments.add_apartment(number='M-202', resident_name='Invited Mobile', resident_email='')
        user_id = user_model.create_user(
            username='mobile_invited',
            email='mobile_invited@example.com',
            password='password123',
            full_name='Invited Mobile',
            role='resident',
        )
        invitation = residents.issue_resident_invitation(
            user_id,
            unit_id,
            resident_email='mobile_invited@example.com',
            resident_name='Invited Mobile',
            created_by=1,
        )

    _login_user_session(client, user_id)

    list_response = client.get('/api/resident/invitations')
    activate_response = client.post('/api/resident/invitations/activate', json={'code': invitation['invitation_code']})

    assert list_response.status_code == 200
    assert len(list_response.get_json()['invitations']) == 1
    assert activate_response.status_code == 200
    assert activate_response.get_json()['apartment']['status'] == 'active'

    with app.app_context():
        assert residents.get_allowed_unit_ids_for_user(user_id) == {unit_id}


@pytest.mark.integration
def test_resident_api_pdf_endpoints_return_files(client, app, monkeypatch):
    with app.app_context():
        _reset_api_state()
        unit_id = apartments.add_apartment(number='M-303', resident_name='PDF API Resident', resident_email='')
        user_id = user_model.create_user(
            username='mobile_pdf',
            email='mobile_pdf@example.com',
            password='password123',
            full_name='PDF API Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='mobile_pdf@example.com',
            resident_name='PDF API Resident',
            created_by=1,
        )

        conn = db.get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO invoices (unit_id, description, amount, issued_date, due_date, paid) VALUES (?, ?, ?, ?, ?, ?)",
                (unit_id, 'Factura PDF API', 200.0, '2026-05-01', '2026-05-15', 0),
            )
            invoice_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()

    invoices_dir = Path(app.root_path) / 'static' / 'invoices'
    invoices_dir.mkdir(parents=True, exist_ok=True)
    (invoices_dir / f'invoice_{invoice_id}.pdf').write_bytes(b'%PDF-1.4\n%resident-api\n')

    def fake_generate_account_statement_pdf(apt, invoices, payments, company_info, output_path=None):
        target_path = Path(output_path)
        target_path.write_bytes(b'%PDF-1.4\n%resident-api-statement\n')

    monkeypatch.setattr(receipt_pdf, 'generate_account_statement_pdf', fake_generate_account_statement_pdf)

    _login_user_session(client, user_id)

    invoice_response = client.get(f'/api/resident/invoices/{invoice_id}/pdf')
    statement_response = client.get(f'/api/resident/apartments/{unit_id}/statement.pdf')

    assert invoice_response.status_code == 200
    assert invoice_response.mimetype == 'application/pdf'
    assert statement_response.status_code == 200
    assert statement_response.mimetype == 'application/pdf'


@pytest.mark.integration
def test_resident_api_mobile_login_returns_tokens_and_bearer_access(client, app):
    with app.app_context():
        _reset_api_state()
        unit_id = apartments.add_apartment(number='JWT-101', resident_name='JWT Resident', resident_email='')
        user_id = user_model.create_user(
            username='jwt_resident',
            email='jwt_resident@example.com',
            password='password123',
            full_name='JWT Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='jwt_resident@example.com',
            resident_name='JWT Resident',
            created_by=1,
        )

    login_response = client.post(
        '/api/resident/auth/login',
        json={'identifier': 'jwt_resident@example.com', 'password': 'password123'},
    )

    assert login_response.status_code == 200
    login_payload = login_response.get_json()
    assert login_payload['tokens']['token_type'] == 'Bearer'
    assert login_payload['tokens']['access_token']
    assert login_payload['tokens']['refresh_token']

    profile_response = client.get(
        '/api/resident/profile',
        headers=_authorization_headers(login_payload['tokens']['access_token']),
    )
    apartments_response = client.get(
        '/api/resident/apartments',
        headers=_authorization_headers(login_payload['tokens']['access_token']),
    )

    assert profile_response.status_code == 200
    assert apartments_response.status_code == 200
    assert profile_response.get_json()['profile']['email'] == 'jwt_resident@example.com'
    assert apartments_response.get_json()['apartments'][0]['number'] == 'JWT-101'


@pytest.mark.integration
def test_resident_api_refresh_issues_new_access_token(client, app):
    with app.app_context():
        _reset_api_state()
        unit_id = apartments.add_apartment(number='JWT-202', resident_name='Refresh Resident', resident_email='')
        user_id = user_model.create_user(
            username='refresh_resident',
            email='refresh_resident@example.com',
            password='password123',
            full_name='Refresh Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='refresh_resident@example.com',
            resident_name='Refresh Resident',
            created_by=1,
        )

    login_response = client.post(
        '/api/resident/auth/login',
        json={'identifier': 'refresh_resident', 'password': 'password123'},
    )
    login_payload = login_response.get_json()

    refresh_response = client.post(
        '/api/resident/auth/refresh',
        json={'refresh_token': login_payload['tokens']['refresh_token']},
    )

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.get_json()
    assert refresh_payload['tokens']['access_token'] != login_payload['tokens']['access_token']
    assert refresh_payload['tokens']['refresh_token'] != login_payload['tokens']['refresh_token']

    reused_refresh_response = client.post(
        '/api/resident/auth/refresh',
        json={'refresh_token': login_payload['tokens']['refresh_token']},
    )

    profile_response = client.get(
        '/api/resident/profile',
        headers=_authorization_headers(refresh_payload['tokens']['access_token']),
    )

    assert reused_refresh_response.status_code == 401
    assert profile_response.status_code == 200
    assert profile_response.get_json()['profile']['username'] == 'refresh_resident'


@pytest.mark.integration
def test_resident_api_bearer_pdf_endpoints_return_files(client, app, monkeypatch):
    with app.app_context():
        _reset_api_state()
        unit_id = apartments.add_apartment(number='JWT-303', resident_name='Bearer PDF Resident', resident_email='')
        user_id = user_model.create_user(
            username='bearer_pdf',
            email='bearer_pdf@example.com',
            password='password123',
            full_name='Bearer PDF Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='bearer_pdf@example.com',
            resident_name='Bearer PDF Resident',
            created_by=1,
        )

        conn = db.get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO invoices (unit_id, description, amount, issued_date, due_date, paid) VALUES (?, ?, ?, ?, ?, ?)",
                (unit_id, 'Factura Bearer PDF', 210.0, '2026-05-01', '2026-05-15', 0),
            )
            invoice_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()

    invoices_dir = Path(app.root_path) / 'static' / 'invoices'
    invoices_dir.mkdir(parents=True, exist_ok=True)
    (invoices_dir / f'invoice_{invoice_id}.pdf').write_bytes(b'%PDF-1.4\n%resident-api-bearer\n')

    def fake_generate_account_statement_pdf(apt, invoices, payments, company_info, output_path=None):
        target_path = Path(output_path)
        target_path.write_bytes(b'%PDF-1.4\n%resident-api-bearer-statement\n')

    monkeypatch.setattr(receipt_pdf, 'generate_account_statement_pdf', fake_generate_account_statement_pdf)

    login_response = client.post(
        '/api/resident/auth/login',
        json={'identifier': 'bearer_pdf@example.com', 'password': 'password123'},
    )
    access_token = login_response.get_json()['tokens']['access_token']

    invoice_response = client.get(
        f'/api/resident/invoices/{invoice_id}/pdf',
        headers=_authorization_headers(access_token),
    )
    statement_response = client.get(
        f'/api/resident/apartments/{unit_id}/statement.pdf',
        headers=_authorization_headers(access_token),
    )

    assert invoice_response.status_code == 200
    assert invoice_response.mimetype == 'application/pdf'
    assert statement_response.status_code == 200
    assert statement_response.mimetype == 'application/pdf'


@pytest.mark.integration
def test_resident_api_logout_revokes_refresh_token(client, app):
    with app.app_context():
        _reset_api_state()
        unit_id = apartments.add_apartment(number='JWT-404', resident_name='Logout Resident', resident_email='')
        user_id = user_model.create_user(
            username='logout_resident',
            email='logout_resident@example.com',
            password='password123',
            full_name='Logout Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='logout_resident@example.com',
            resident_name='Logout Resident',
            created_by=1,
        )

    login_response = client.post(
        '/api/resident/auth/login',
        json={'identifier': 'logout_resident@example.com', 'password': 'password123'},
    )
    login_payload = login_response.get_json()

    logout_response = client.post(
        '/api/resident/auth/logout',
        json={'refresh_token': login_payload['tokens']['refresh_token']},
        headers=_authorization_headers(login_payload['tokens']['access_token']),
    )

    refresh_after_logout_response = client.post(
        '/api/resident/auth/refresh',
        json={'refresh_token': login_payload['tokens']['refresh_token']},
    )

    assert logout_response.status_code == 200
    assert logout_response.get_json()['revoked_tokens'] == 1
    assert refresh_after_logout_response.status_code == 401