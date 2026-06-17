import pytest
import app as app_module

import apartments
import db
import receipt_pdf
import residents
import user_model


def _reset_resident_link_state():
    conn = db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM resident_user_units")
        cur.execute("DELETE FROM payments")
        cur.execute("DELETE FROM invoices")
        cur.execute("DELETE FROM residents")
        cur.execute("DELETE FROM apartments")
        cur.execute("DELETE FROM users WHERE username != 'admin'")
        conn.commit()
    finally:
        conn.close()


@pytest.mark.unit
def test_link_user_to_apartment_creates_bridge_and_legacy_assignment(app):
    with app.app_context():
        _reset_resident_link_state()
        unit_id = apartments.add_apartment(number='A-101', resident_email='')
        user_id = user_model.create_user(
            username='resident_linked',
            email='resident_linked@example.com',
            password='password123',
            full_name='Resident Linked',
            role='resident',
        )

        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='resident_linked@example.com',
            resident_name='Resident Linked',
            created_by=1,
        )

        conn = db.get_conn()
        try:
            row = conn.execute(
                """
                SELECT user_id, unit_id, status, is_primary
                FROM resident_user_units
                WHERE user_id = ? AND unit_id = ?
                """,
                (user_id, unit_id),
            ).fetchone()
        finally:
            conn.close()

        apartment = apartments.get_apartment(unit_id)

    assert row is not None
    assert row['status'] == 'active'
    assert row['is_primary'] == 1
    assert apartment['resident_email'] == 'resident_linked@example.com'
    assert apartment['resident_name'] == 'Resident Linked'
    assert residents.get_allowed_unit_ids_for_user(user_id) == {unit_id}


@pytest.mark.unit
def test_list_linked_apartments_for_user_falls_back_to_legacy_email(app):
    with app.app_context():
        _reset_resident_link_state()
        unit_id = apartments.add_apartment(
            number='B-202',
            resident_name='Legacy Resident',
            resident_email='legacy@example.com',
        )
        user_id = user_model.create_user(
            username='legacy_resident',
            email='legacy@example.com',
            password='password123',
            full_name='Legacy Resident',
            role='resident',
        )

        linked_apartments = residents.list_linked_apartments_for_user(
            user_id,
            fallback_email='legacy@example.com',
        )

    assert len(linked_apartments) == 1
    assert linked_apartments[0]['id'] == unit_id
    assert linked_apartments[0]['resident_email'] == 'legacy@example.com'


@pytest.mark.unit
def test_issue_and_activate_resident_invitation_code(app):
    with app.app_context():
        _reset_resident_link_state()
        unit_id = apartments.add_apartment(number='I-505', resident_name='Invited Resident', resident_email='')
        user_id = user_model.create_user(
            username='invited_resident',
            email='invited_resident@example.com',
            password='password123',
            full_name='Invited Resident',
            role='resident',
        )

        invitation = residents.issue_resident_invitation(
            user_id,
            unit_id,
            resident_email='invited_resident@example.com',
            resident_name='Invited Resident',
            created_by=1,
        )
        pending_invitations = residents.list_pending_invitations_for_user(user_id)
        allowed_before_activation = residents.get_allowed_unit_ids_for_user(user_id)

        activated_apartment = residents.activate_resident_invitation(
            user_id,
            invitation['invitation_code'],
            resident_email='invited_resident@example.com',
            resident_name='Invited Resident',
        )
        allowed_after_activation = residents.get_allowed_unit_ids_for_user(user_id)

        conn = db.get_conn()
        try:
            row = conn.execute(
                "SELECT status, invitation_code, activated_at FROM resident_user_units WHERE user_id = ? AND unit_id = ?",
                (user_id, unit_id),
            ).fetchone()
        finally:
            conn.close()

    assert invitation['status'] == 'invited'
    assert invitation['invitation_code']
    assert len(pending_invitations) == 1
    assert allowed_before_activation == set()
    assert activated_apartment['status'] == 'active'
    assert allowed_after_activation == {unit_id}
    assert row['status'] == 'active'
    assert row['invitation_code'] is None
    assert row['activated_at']



@pytest.mark.integration
def test_resident_dashboard_uses_bridge_assignment_without_legacy_email(client, app):
    with app.app_context():
        _reset_resident_link_state()
        unit_id = apartments.add_apartment(number='C-303', resident_name='Bridge Resident', resident_email='')
        conn = db.get_conn()
        try:
            conn.execute(
                "INSERT INTO invoices (unit_id, description, amount, issued_date, paid) VALUES (?, ?, ?, ?, ?)",
                (unit_id, 'Mantenimiento junio', 150.0, '2026-06-01', 0),
            )
            conn.commit()
        finally:
            conn.close()

        user_id = user_model.create_user(
            username='bridge_dashboard',
            email='bridge_dashboard@example.com',
            password='password123',
            full_name='Bridge Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_name='Bridge Resident',
            created_by=1,
        )

    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True

    response = client.get('/dashboard')

    assert response.status_code == 200
    assert b'C-303' in response.data
    assert b'Mantenimiento junio' in response.data


@pytest.mark.integration
def test_resident_section_routes_and_help_answer_render(client, app):
    with app.app_context():
        _reset_resident_link_state()
        unit_id = apartments.add_apartment(number='E-505', resident_name='Portal Resident', resident_email='')
        conn = db.get_conn()
        try:
            conn.execute(
                "INSERT INTO invoices (unit_id, description, amount, issued_date, paid) VALUES (?, ?, ?, ?, ?)",
                (unit_id, 'Cuota portal', 200.0, '2026-06-01', 0),
            )
            conn.commit()
        finally:
            conn.close()

        user_id = user_model.create_user(
            username='portal_resident',
            email='portal_resident@example.com',
            password='password123',
            full_name='Portal Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='portal_resident@example.com',
            resident_name='Portal Resident',
            created_by=1,
        )

    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True

    balances_response = client.get('/dashboard')
    evolution_response = client.get('/dashboard/evolucion')
    billing_response = client.get('/dashboard/facturas-pagos')
    reports_response = client.get('/dashboard/reportes')
    help_response = client.get('/dashboard/ayuda?q=Cuantas%20facturas%20pendientes%20tengo')

    assert balances_response.status_code == 200
    assert evolution_response.status_code == 200
    assert billing_response.status_code == 200
    assert reports_response.status_code == 200
    assert help_response.status_code == 200

    assert 'Balance y estado actual' in balances_response.get_data(as_text=True)
    assert 'Evolución y distribución' in evolution_response.get_data(as_text=True)
    assert 'Facturas pendientes e histórico' in billing_response.get_data(as_text=True)
    assert 'Reportes y PDF económicos' in reports_response.get_data(as_text=True)
    assert 'Estado de facturas pendientes' in help_response.get_data(as_text=True)


@pytest.mark.integration
def test_resident_help_ai_chat_uses_external_provider_when_configured(client, app, monkeypatch):
    with app.app_context():
        _reset_resident_link_state()
        unit_id = apartments.add_apartment(number='F-606', resident_name='AI Resident', resident_email='')
        user_id = user_model.create_user(
            username='ai_resident',
            email='ai_resident@example.com',
            password='password123',
            full_name='AI Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='ai_resident@example.com',
            resident_name='AI Resident',
            created_by=1,
        )

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                'choices': [
                    {
                        'message': {
                            'content': 'Tu balance pendiente sigue activo y puedes revisarlo en Balances o Facturas y pagos.'
                        }
                    }
                ]
            }

    def _fake_post(url, headers=None, json=None, timeout=None):
        assert json['model'] == 'demo-model'
        assert json['messages'][-1]['content'] == 'Explicame mi balance actual'
        return _FakeResponse()

    monkeypatch.setattr(app_module.requests, 'post', _fake_post)
    app.config.update({
        'RESIDENT_AI_CHAT_ENABLED': True,
        'RESIDENT_AI_API_URL': 'https://example.com/v1/chat/completions',
        'RESIDENT_AI_API_KEY': 'test-key',
        'RESIDENT_AI_MODEL': 'demo-model',
    })

    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True

    response = client.get('/dashboard/ayuda?q=Explicame%20mi%20balance%20actual', follow_redirects=True)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'IA conectada' in body
    assert 'Toscana IA' in body
    assert 'Tu balance pendiente sigue activo y puedes revisarlo en Balances o Facturas y pagos.' in body


@pytest.mark.integration
def test_resident_help_chat_post_persists_and_reset_clears_thread(client, app):
    with app.app_context():
        _reset_resident_link_state()
        unit_id = apartments.add_apartment(number='G-707', resident_name='Chat Resident', resident_email='')
        user_id = user_model.create_user(
            username='chat_resident',
            email='chat_resident@example.com',
            password='password123',
            full_name='Chat Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='chat_resident@example.com',
            resident_name='Chat Resident',
            created_by=1,
        )

    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True

    response = client.post(
        '/dashboard/ayuda',
        data={'question': 'Cual es mi saldo actual?'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    response_text = response.get_data(as_text=True)
    assert 'Cual es mi saldo actual?' in response_text
    assert 'Balance actual de tu cuenta' in response_text

    with client.session_transaction() as session:
        thread_keys = [key for key in session.keys() if key.startswith('resident_help_thread_')]
        assert thread_keys
        assert len(session[thread_keys[0]]) == 2

    reset_response = client.get('/dashboard/ayuda?action=reset', follow_redirects=True)

    assert reset_response.status_code == 200
    assert 'Inicia una conversación con una pregunta sobre tu cuenta' in reset_response.get_data(as_text=True)

    with client.session_transaction() as session:
        assert not any(key.startswith('resident_help_thread_') for key in session.keys())


@pytest.mark.integration
def test_resident_help_understands_question_variations_for_debt_payments_and_units(client, app):
    with app.app_context():
        _reset_resident_link_state()
        unit_id = apartments.add_apartment(number='J-808', resident_name='Variation Resident', resident_email='')
        user_id = user_model.create_user(
            username='variation_resident',
            email='variation_resident@example.com',
            password='password123',
            full_name='Variation Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='variation_resident@example.com',
            resident_name='Variation Resident',
            created_by=1,
        )

        conn = db.get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO invoices (unit_id, description, amount, issued_date, due_date, paid) VALUES (?, ?, ?, ?, ?, ?)",
                (unit_id, 'Cuota variacion', 180.0, '2026-06-01', '2026-06-15', 0),
            )
            invoice_id = cur.lastrowid
            cur.execute(
                "INSERT INTO payments (invoice_id, amount, paid_date, method, notes) VALUES (?, ?, ?, ?, ?)",
                (invoice_id, 60.0, '2026-06-08', 'transfer', 'Abono parcial'),
            )
            conn.commit()
        finally:
            conn.close()

    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True

    debt_response = client.get('/dashboard/ayuda?q=Sigo%20adeudando%20algo%20o%20ya%20estoy%20al%20dia')
    payments_response = client.get('/dashboard/ayuda?q=Ensename%20mis%20ultimos%20abonos%20registrados')
    units_response = client.get('/dashboard/ayuda?q=Que%20inmuebles%20tengo%20asociados%20en%20el%20portal')

    assert debt_response.status_code == 200
    assert payments_response.status_code == 200
    assert units_response.status_code == 200

    debt_text = debt_response.get_data(as_text=True)
    payments_text = payments_response.get_data(as_text=True)
    units_text = units_response.get_data(as_text=True)

    assert 'Estado actual de tu cuenta' in debt_text or 'Balance actual de tu cuenta' in debt_text
    assert 'RD$' in debt_text
    assert 'Pagos recientes' in payments_text
    assert 'Abono parcial' in payments_text or 'transfer' in payments_text
    assert 'Tus unidades vinculadas' in units_text
    assert 'J-808' in units_text


@pytest.mark.integration
def test_resident_help_returns_portal_summary_for_generic_capability_question(client, app):
    with app.app_context():
        _reset_resident_link_state()
        unit_id = apartments.add_apartment(number='K-909', resident_name='Capability Resident', resident_email='')
        user_id = user_model.create_user(
            username='capability_resident',
            email='capability_resident@example.com',
            password='password123',
            full_name='Capability Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='capability_resident@example.com',
            resident_name='Capability Resident',
            created_by=1,
        )

    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True

    response = client.get('/dashboard/ayuda?q=Que%20informacion%20del%20portal%20puedes%20responderme')

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Informacion disponible en tu portal' in body
    assert 'saldo, facturas, pagos, unidades vinculadas' in body


@pytest.mark.integration
def test_download_statement_pdf_allows_bridge_linked_resident(client, app, monkeypatch, tmp_path):
    with app.app_context():
        _reset_resident_link_state()
        unit_id = apartments.add_apartment(number='D-404', resident_name='PDF Resident', resident_email='')
        user_id = user_model.create_user(
            username='bridge_pdf',
            email='bridge_pdf@example.com',
            password='password123',
            full_name='PDF Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_name='PDF Resident',
            created_by=1,
        )

    def fake_generate_account_statement_pdf(apt, invoices, payments, company_info, output_path=None):
        target_path = output_path or tmp_path / 'statement.pdf'
        with open(target_path, 'wb') as handle:
            handle.write(b'%PDF-1.4\n%bridge\n')

    monkeypatch.setattr(receipt_pdf, 'generate_account_statement_pdf', fake_generate_account_statement_pdf)

    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True

    response = client.get(f'/ventas/apartamentos/estado-cuenta/{unit_id}')

    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'


@pytest.mark.integration
def test_resident_help_api_ajax_endpoint(client, app):
    with app.app_context():
        _reset_resident_link_state()
        unit_id = apartments.add_apartment(number='H-808', resident_name='AJAX Resident', resident_email='')
        user_id = user_model.create_user(
            username='ajax_resident',
            email='ajax_resident@example.com',
            password='password123',
            full_name='AJAX Resident',
            role='resident',
        )
        residents.link_user_to_apartment(
            user_id,
            unit_id,
            resident_email='ajax_resident@example.com',
            resident_name='AJAX Resident',
            created_by=1,
        )

    # Test unauthorized access (should return 302 redirecting to login)
    response = client.post('/dashboard/ayuda/api', json={'question': 'Hola'})
    assert response.status_code == 302

    # Log in
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True

    # Test empty question
    response = client.post('/dashboard/ayuda/api', json={'question': ''})
    assert response.status_code == 400
    assert response.get_json() == {'error': 'empty_question'}

    # Test valid question (triggers deterministic response since AI config is disabled by default)
    response = client.post('/dashboard/ayuda/api', json={'question': 'Cual es mi saldo actual?'})
    assert response.status_code == 200
    data = response.get_json()
    assert 'answer' in data
    assert data['answer'] is not None
    assert 'Balance actual' in data['answer']['title'] or 'Estado actual' in data['answer']['title']

    # Verify session thread has been populated with both messages
    with client.session_transaction() as session:
        thread_keys = [key for key in session.keys() if key.startswith('resident_help_thread_')]
        assert thread_keys
        assert len(session[thread_keys[0]]) == 2
        assert session[thread_keys[0]][0]['content'] == 'Cual es mi saldo actual?'
        assert session[thread_keys[0]][1]['role'] == 'assistant'