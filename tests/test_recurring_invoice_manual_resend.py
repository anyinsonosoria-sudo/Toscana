import uuid
from pathlib import Path

import db
from blueprints import billing as billing_blueprint


def _clear_recurring_invoice_fixtures():
    with db.get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM invoices WHERE unit_id IN (SELECT id FROM apartments WHERE number LIKE 'RR-%' OR number LIKE 'RI-%')"
        )
        cur.execute(
            "DELETE FROM recurring_sales WHERE unit_id IN (SELECT id FROM apartments WHERE number LIKE 'RR-%' OR number LIKE 'RI-%')"
        )
        cur.execute("DELETE FROM apartments WHERE number LIKE 'RR-%' OR number LIKE 'RI-%'")
        conn.commit()


def _create_recurring_invoice_fixture(*, resident_email='cliente@example.com', active=1):
    unique_id = uuid.uuid4().hex[:8]
    with db.get_db() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO apartments(number, floor, resident_name, resident_email, resident_phone)
            VALUES(?, ?, ?, ?, ?)
            """,
            (f'RR-{unique_id}', '1', 'Cliente Recurrente', resident_email, '8090000000'),
        )
        unit_id = cur.lastrowid

        cur.execute(
            """
            INSERT INTO recurring_sales(unit_id, service_id, amount, frequency, billing_day,
                                        start_date, description, active, last_generated)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (unit_id, None, 1000.0, 'monthly', 25, '2026-02-25', 'Cargo mantenimiento', active, '2026-05-25'),
        )
        sale_id = cur.lastrowid

        cur.execute(
            """
            INSERT INTO invoices(unit_id, description, amount, issued_date, due_date, paid, pending_amount, recurring_sale_id)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (unit_id, 'Cargo mantenimiento', 1000.0, '2026-05-25', '2026-06-24', 0, 1000.0, sale_id),
        )
        invoice_id = cur.lastrowid

        conn.commit()

    return {
        'unit_id': unit_id,
        'sale_id': sale_id,
        'invoice_id': invoice_id,
        'resident_email': resident_email,
    }


def test_send_invoice_email_attaches_existing_pdf(app, monkeypatch):
    _clear_recurring_invoice_fixtures()
    fixture = _create_recurring_invoice_fixture()
    conn = db.get_conn()
    invoice = conn.execute('SELECT * FROM invoices WHERE id = ?', (fixture['invoice_id'],)).fetchone()
    conn.close()
    invoice = dict(invoice)
    captured = []

    pdf_file = Path(__file__).parent.parent / 'static' / 'invoices' / f"invoice_{fixture['invoice_id']}.pdf"
    pdf_file.parent.mkdir(parents=True, exist_ok=True)
    pdf_file.write_bytes(b'%PDF-1.4 test')

    try:
        import senders

        def fake_send_invoice_notification(invoice, unit, client_email=None, admin_email=None,
                                           attach_pdf=False, pdf_path=None, client_phone=None):
            captured.append({
                'invoice': invoice,
                'unit': unit,
                'client_email': client_email,
                'admin_email': admin_email,
                'attach_pdf': attach_pdf,
                'pdf_path': pdf_path,
                'client_phone': client_phone,
            })

        monkeypatch.setattr(senders, 'send_invoice_notification', fake_send_invoice_notification)

        result = billing_blueprint._send_invoice_email(
            invoice,
            client_email=fixture['resident_email'],
            attach_pdf=True,
            admin_email='admin@example.com',
        )

        assert result['attach_pdf'] is True
        assert result['pdf_path'] == str(pdf_file)
        assert len(captured) == 1
        assert captured[0]['attach_pdf'] is True
        assert captured[0]['pdf_path'] == str(pdf_file)
        assert captured[0]['client_email'] == fixture['resident_email']
        assert captured[0]['admin_email'] == 'admin@example.com'
        assert captured[0]['invoice']['resident_name'] == 'Cliente Recurrente'
        assert captured[0]['client_phone'] is None
    finally:
        if pdf_file.exists():
            pdf_file.unlink()


def test_resend_latest_recurring_invoices_sends_existing_latest_invoice(auth_client, monkeypatch):
    _clear_recurring_invoice_fixtures()
    fixture = _create_recurring_invoice_fixture()
    _create_recurring_invoice_fixture(resident_email='', active=1)
    _create_recurring_invoice_fixture(resident_email='inactivo@example.com', active=0)

    captured = []

    monkeypatch.setattr(billing_blueprint, '_get_admin_email', lambda: 'admin@example.com')

    def fake_send_invoice_email(invoice, client_email=None, attach_pdf=False, admin_email=None):
        captured.append({
            'invoice': invoice,
            'client_email': client_email,
            'attach_pdf': attach_pdf,
            'admin_email': admin_email,
        })

    monkeypatch.setattr(billing_blueprint, '_send_invoice_email', fake_send_invoice_email)

    response = auth_client.post('/ventas/facturas/recurring/resend-latest', data={}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/ventas/recurrentes')
    assert len(captured) == 1
    assert captured[0]['invoice']['id'] == fixture['invoice_id']
    assert captured[0]['client_email'] == fixture['resident_email']
    assert captured[0]['attach_pdf'] is True
    assert captured[0]['admin_email'] == 'admin@example.com'