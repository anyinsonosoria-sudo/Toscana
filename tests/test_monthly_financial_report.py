from datetime import datetime

import pytest

import senders
from company import get_company_info
from db import get_conn
from extensions import scheduler
from receipt_pdf import generate_monthly_financial_report_pdf
from reports import (
    claim_monthly_report_dispatch,
    get_monthly_financial_report_data,
    get_monthly_report_recipients,
    mark_monthly_report_dispatch_sent,
    send_previous_month_financial_report,
)
from senders import generate_monthly_financial_report_html


def _seed_monthly_report_data():
    conn = get_conn()
    try:
        cur = conn.cursor()

        for table in (
            'monthly_report_dispatch_log',
            'payments',
            'invoices',
            'expenses',
            'accounting_transactions',
            'residents',
            'apartments',
            'company_info',
        ):
            cur.execute(f'DELETE FROM {table}')

        cur.execute(
            """
            INSERT INTO company_info (name, email, phone, address)
            VALUES (?, ?, ?, ?)
            """,
            ('Condominio Toscana', 'ADMIN@TOSCANA.COM', '8090000000', 'Santo Domingo'),
        )

        cur.execute(
            """
            INSERT INTO apartments (number, resident_name, resident_email)
            VALUES (?, ?, ?)
            """,
            ('A-101', 'Ana Perez', 'Ana@example.com '),
        )
        unit_1 = cur.lastrowid

        cur.execute(
            """
            INSERT INTO apartments (number, resident_name, resident_email)
            VALUES (?, ?, ?)
            """,
            ('B-202', 'Bruno Diaz', 'BRUNO@example.com'),
        )
        unit_2 = cur.lastrowid

        cur.executemany(
            """
            INSERT INTO residents (unit_id, name, email, role)
            VALUES (?, ?, ?, ?)
            """,
            [
                (unit_1, 'Ana Perez', 'ana@example.com', 'owner'),
                (unit_2, 'Bruno Diaz', 'bruno@example.com', 'tenant'),
                (unit_2, 'Carla Soto', 'carla@example.com', 'tenant'),
            ],
        )

        cur.execute(
            """
            INSERT INTO invoices (unit_id, description, amount, issued_date, due_date, paid)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (unit_1, 'Mantenimiento abril', 100.0, '2026-04-02', '2026-04-30', 0),
        )
        april_invoice_paid = cur.lastrowid

        cur.execute(
            """
            INSERT INTO invoices (unit_id, description, amount, issued_date, due_date, paid)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (unit_2, 'Mantenimiento abril', 200.0, '2026-04-05', '2026-04-30', 0),
        )

        cur.execute(
            """
            INSERT INTO invoices (unit_id, description, amount, issued_date, due_date, paid)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (unit_1, 'Mantenimiento marzo', 50.0, '2026-03-01', '2026-03-31', 1),
        )
        march_invoice = cur.lastrowid

        cur.executemany(
            """
            INSERT INTO payments (invoice_id, amount, paid_date, method)
            VALUES (?, ?, ?, ?)
            """,
            [
                (march_invoice, 50.0, '2026-03-15 09:00:00', 'transferencia'),
                (april_invoice_paid, 75.0, '2026-04-10 10:00:00', 'transferencia'),
            ],
        )

        cur.executemany(
            """
            INSERT INTO expenses (description, amount, category, date, payment_method)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ('Compra de bombillos', 20.0, 'Mantenimiento', '2026-03-20', 'transferencia'),
                ('Limpieza áreas comunes', 30.0, 'Operaciones', '2026-04-12', 'efectivo'),
            ],
        )

        conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope='module')
def preview_auth_client(app):
    client = app.test_client()

    with app.app_context():
        conn = get_conn()
        try:
            admin_row = conn.execute(
                "SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1"
            ).fetchone()
        finally:
            conn.close()

    assert admin_row is not None

    with client.session_transaction() as session:
        session['_user_id'] = str(admin_row['id'])
        session['_fresh'] = True

    yield client


@pytest.mark.unit
def test_get_monthly_financial_report_data_uses_previous_month(app):
    with app.app_context():
        _seed_monthly_report_data()
        report = get_monthly_financial_report_data(reference_dt=datetime(2026, 5, 3, 8, 0, 0))

    assert report['report_period'] == '2026-04'
    assert report['date_from'] == '2026-04-01'
    assert report['date_to'] == '2026-04-30'
    assert report['period_label'] == 'Abril 2026'
    assert report['opening_balance'] == pytest.approx(30.0)
    assert report['total_collections'] == pytest.approx(75.0)
    assert report['total_pending_receivables'] == pytest.approx(225.0)
    assert report['total_expenses'] == pytest.approx(30.0)
    assert report['closing_balance'] == pytest.approx(75.0)
    assert len(report['collections']) == 1
    assert report['collections'][0]['apt_number'] == 'A-101'
    assert report['pending_receivables'][0]['days_overdue'] == 0
    assert len(report['expenses']) == 1
    assert report['expenses'][0]['description'] == 'Limpieza áreas comunes'


@pytest.mark.unit
def test_monthly_report_pending_days_overdue_never_negative(app):
    with app.app_context():
        _seed_monthly_report_data()
        conn = get_conn()
        try:
            unit_id = conn.execute("SELECT id FROM apartments WHERE number = ?", ('B-202',)).fetchone()['id']
            conn.execute(
                """
                INSERT INTO invoices (unit_id, description, amount, issued_date, due_date, paid)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (unit_id, 'Mantenimiento mayo', 180.0, '2026-04-28', '2026-05-20', 0),
            )
            conn.commit()
        finally:
            conn.close()

        report = get_monthly_financial_report_data(reference_dt=datetime(2026, 5, 3, 8, 0, 0))

    future_due_invoice = next(item for item in report['pending_receivables'] if item['description'] == 'Mantenimiento mayo')
    assert future_due_invoice['days_overdue'] == 0


@pytest.mark.unit
def test_get_monthly_report_recipients_deduplicates_emails(app):
    with app.app_context():
        _seed_monthly_report_data()
        recipients = get_monthly_report_recipients()

    all_emails = [recipient['email'] for recipient in recipients['all_recipients']]

    assert recipients['admin_email'] == 'admin@toscana.com'
    assert all_emails == [
        'admin@toscana.com',
        'ana@example.com',
        'bruno@example.com',
        'carla@example.com',
    ]


@pytest.mark.unit
def test_get_monthly_financial_report_data_supports_current_month_to_date(app):
    with app.app_context():
        _seed_monthly_report_data()
        report = get_monthly_financial_report_data(
            reference_dt=datetime(2026, 4, 12, 8, 0, 0),
            period_mode='current_month_to_date',
        )

    assert report['report_period'] == '2026-04'
    assert report['date_from'] == '2026-04-01'
    assert report['date_to'] == '2026-04-12'
    assert report['period_mode'] == 'current_month_to_date'
    assert report['is_partial_period'] is True
    assert report['period_mode_label'] == 'Mes actual a la fecha'
    assert report['period_label'] == 'Abril 2026 (al 12/04/2026)'
    assert report['opening_balance'] == pytest.approx(30.0)
    assert report['total_collections'] == pytest.approx(75.0)
    assert report['total_pending_receivables'] == pytest.approx(225.0)
    assert report['total_expenses'] == pytest.approx(30.0)
    assert report['closing_balance'] == pytest.approx(75.0)


@pytest.mark.unit
def test_monthly_report_dispatch_log_blocks_duplicate_send(app):
    with app.app_context():
        _seed_monthly_report_data()

        first_claim = claim_monthly_report_dispatch('2026-04', ' admin@toscana.com ')
        mark_monthly_report_dispatch_sent('2026-04', 'ADMIN@toscana.com', subject='Reporte Abril 2026')
        second_claim = claim_monthly_report_dispatch('2026-04', 'admin@toscana.com')

        conn = get_conn()
        try:
            row = conn.execute(
                """
                SELECT status, subject, recipient_email
                FROM monthly_report_dispatch_log
                WHERE report_type = 'monthly_financial_report'
                  AND report_period = ?
                  AND recipient_email = ?
                """,
                ('2026-04', 'admin@toscana.com'),
            ).fetchone()
        finally:
            conn.close()

    assert first_claim is True
    assert second_claim is False
    assert row['status'] == 'sent'
    assert row['subject'] == 'Reporte Abril 2026'
    assert row['recipient_email'] == 'admin@toscana.com'


@pytest.mark.integration
def test_generate_monthly_financial_report_pdf_creates_file(app, tmp_path):
    with app.app_context():
        _seed_monthly_report_data()
        report = get_monthly_financial_report_data(reference_dt=datetime(2026, 5, 3, 8, 0, 0))
        company_info = get_company_info()
        pdf_path = tmp_path / 'monthly_financial_report_2026-04.pdf'

        generate_monthly_financial_report_pdf(report, company_info, output_path=str(pdf_path))

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


@pytest.mark.unit
def test_generate_monthly_financial_report_html_includes_highlights(app):
    with app.app_context():
        _seed_monthly_report_data()
        report = get_monthly_financial_report_data(reference_dt=datetime(2026, 5, 3, 8, 0, 0))
        html = generate_monthly_financial_report_html(
            report,
            recipient_name='Administrador',
            recipient_type='admin',
            company_name='Condominio Toscana',
        )

    assert 'Resumen ejecutivo' in html
    assert 'Cobros destacados' in html
    assert 'Pendientes del cierre' in html
    assert 'Variación neta' in html


@pytest.mark.integration
def test_send_previous_month_financial_report_sends_once_per_unique_recipient(app, monkeypatch, tmp_path):
    sent_messages = []

    def fake_send_email(to_email, subject, html, attach_pdf=None, attachments=None):
        sent_messages.append({
            'to_email': to_email,
            'subject': subject,
            'html': html,
            'attachments': attachments,
        })

    monkeypatch.setattr(senders, 'send_email', fake_send_email)

    with app.app_context():
        _seed_monthly_report_data()
        pdf_path = tmp_path / 'monthly_financial_report_2026-04.pdf'

        first_result = send_previous_month_financial_report(
            reference_dt=datetime(2026, 5, 3, 8, 0, 0),
            output_path=str(pdf_path),
        )
        second_result = send_previous_month_financial_report(
            reference_dt=datetime(2026, 5, 3, 8, 0, 0),
            output_path=str(pdf_path),
        )

    assert [message['to_email'] for message in sent_messages] == [
        'admin@toscana.com',
        'ana@example.com',
        'bruno@example.com',
        'carla@example.com',
    ]
    assert all(not isinstance(message['to_email'], list) for message in sent_messages)
    assert all(message['attachments'][0][0] == str(pdf_path) for message in sent_messages)
    assert first_result['failed'] == []
    assert first_result['sent'] == [
        'admin@toscana.com',
        'ana@example.com',
        'bruno@example.com',
        'carla@example.com',
    ]
    assert second_result['sent'] == []
    assert second_result['failed'] == []
    assert second_result['skipped'] == [
        'admin@toscana.com',
        'ana@example.com',
        'bruno@example.com',
        'carla@example.com',
    ]


@pytest.mark.integration
def test_monthly_report_preview_route_renders(preview_auth_client, app):
    with app.app_context():
        _seed_monthly_report_data()

    response = preview_auth_client.get('/reportes/mensual/preview?reference_date=2026-05-03')

    assert response.status_code == 200
    assert b'Vista previa del reporte financiero mensual' in response.data
    assert b'Abril 2026' in response.data
    assert b'Cobros incluidos' in response.data


@pytest.mark.integration
def test_monthly_report_preview_route_supports_current_month_to_date(preview_auth_client, app):
    with app.app_context():
        _seed_monthly_report_data()

    response = preview_auth_client.get(
        '/reportes/mensual/preview?reference_date=2026-04-12&period_mode=current_month_to_date'
    )

    assert response.status_code == 200
    assert b'Mes actual a la fecha' in response.data
    assert b'Abril 2026 (al 12/04/2026)' in response.data
    assert b'Este corte es parcial' in response.data


@pytest.mark.integration
def test_monthly_report_preview_pdf_route_returns_pdf(preview_auth_client, app):
    with app.app_context():
        _seed_monthly_report_data()

    response = preview_auth_client.get('/reportes/mensual/preview.pdf?reference_date=2026-05-03')

    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
    assert len(response.data) > 0


@pytest.mark.integration
def test_monthly_report_preview_pdf_route_supports_current_month_to_date(preview_auth_client, app):
    with app.app_context():
        _seed_monthly_report_data()

    response = preview_auth_client.get(
        '/reportes/mensual/preview.pdf?reference_date=2026-04-12&period_mode=current_month_to_date'
    )

    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
    assert len(response.data) > 0


@pytest.mark.integration
def test_send_previous_month_financial_report_admin_only_sends_only_admin(app, monkeypatch, tmp_path):
    sent_messages = []

    def fake_send_email(to_email, subject, html, attach_pdf=None, attachments=None):
        sent_messages.append({
            'to_email': to_email,
            'subject': subject,
            'html': html,
            'attachments': attachments,
        })

    monkeypatch.setattr(senders, 'send_email', fake_send_email)

    with app.app_context():
        _seed_monthly_report_data()
        pdf_path = tmp_path / 'monthly_financial_report_2026-04-admin-only.pdf'

        result = send_previous_month_financial_report(
            reference_dt=datetime(2026, 5, 3, 8, 0, 0),
            output_path=str(pdf_path),
            admin_only=True,
            admin_email_override='invoicetoscana@gmail.com',
        )

    assert result['admin_only'] is True
    assert result['resolved_admin_email'] == 'invoicetoscana@gmail.com'
    assert result['sent'] == ['invoicetoscana@gmail.com']
    assert result['skipped'] == []
    assert result['failed'] == []
    assert [message['to_email'] for message in sent_messages] == ['invoicetoscana@gmail.com']
    assert all(message['attachments'][0][0] == str(pdf_path) for message in sent_messages)


@pytest.mark.integration
def test_scheduler_registers_monthly_financial_report_job(app):
    job = scheduler.get_job('send_monthly_financial_report')

    assert job is not None
    assert job.id == 'send_monthly_financial_report'
    assert "day='1'" in str(job.trigger)