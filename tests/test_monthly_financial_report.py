from datetime import datetime
import sys

import pytest

import customization
import reports as reports_module
import senders
from scripts import send_monthly_report as monthly_report_cli
from company import get_company_info
from db import get_conn
from extensions import scheduler
from receipt_pdf import generate_monthly_financial_report_pdf
from reports import (
    build_monthly_report_dispatch_summary,
    claim_monthly_report_dispatch,
    dispatch_monthly_financial_report,
    get_monthly_financial_report_data,
    get_monthly_report_settings,
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


def _clear_monthly_report_settings():
    conn = get_conn()
    try:
        conn.execute(
            """
            DELETE FROM customization_settings
            WHERE setting_key IN (
                'monthly_financial_report_enabled',
                'monthly_financial_report_admin_only',
                'monthly_financial_report_admin_email'
            )
            """
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


@pytest.fixture(scope='function')
def operator_client(app):
    client = app.test_client()

    with app.app_context():
        conn = get_conn()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO users (username, email, password_hash, full_name, role, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    'operator_monthly_send',
                    'operator_monthly_send@example.com',
                    'test-hash',
                    'Operador Monthly Send',
                    'operator',
                    1,
                ),
            )
            conn.commit()
            operator_row = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                ('operator_monthly_send',),
            ).fetchone()
        finally:
            conn.close()

    assert operator_row is not None

    with client.session_transaction() as session:
        session['_user_id'] = str(operator_row['id'])
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
def test_get_monthly_report_settings_supports_customization_overrides(app):
    with app.app_context():
        _clear_monthly_report_settings()
        customization.set_setting('monthly_financial_report_enabled', '0')
        customization.set_setting('monthly_financial_report_admin_only', '1')
        customization.set_setting('monthly_financial_report_admin_email', 'REPORTES@TOSCANA.COM')

        settings = get_monthly_report_settings(app.config)

        _clear_monthly_report_settings()

    assert settings['enabled'] is False
    assert settings['admin_only'] is True
    assert settings['admin_email'] == 'reportes@toscana.com'
    assert settings['schedule_day'] == 1


@pytest.mark.unit
def test_dispatch_monthly_financial_report_respects_disabled_setting(app, monkeypatch):
    with app.app_context():
        _clear_monthly_report_settings()
        customization.set_setting('monthly_financial_report_enabled', '0')

        called = {'value': False}

        def fake_send_previous_month_financial_report(*args, **kwargs):
            called['value'] = True
            return {}

        monkeypatch.setattr(reports_module, 'send_previous_month_financial_report', fake_send_previous_month_financial_report)

        result = dispatch_monthly_financial_report(
            reference_dt=datetime(2026, 5, 3, 8, 0, 0),
            app_config=app.config,
            respect_enabled_setting=True,
        )

        _clear_monthly_report_settings()

    assert called['value'] is False
    assert result['status'] == 'disabled'
    assert result['summary']['message'] == 'Reporte financiero mensual deshabilitado por configuración.'


@pytest.mark.unit
def test_build_monthly_report_dispatch_summary_returns_warning_detail_for_failures():
    summary = build_monthly_report_dispatch_summary({
        'report_period': '2026-04',
        'sent': ['ana@example.com'],
        'skipped': ['bruno@example.com'],
        'failed': [{'email': 'carla@example.com', 'error': 'SMTP error'}],
        'status': 'processed',
    })

    assert summary['category'] == 'warning'
    assert summary['message'] == 'Reporte 2026-04 procesado: 1 enviados, 1 omitidos y 1 con error.'
    assert summary['detail'] == 'Primer error de envío para carla@example.com: SMTP error'


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
    assert b'Enviar a residentes' in response.data


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
def test_update_monthly_report_settings_route_persists_configuration(auth_client, app):
    with app.app_context():
        _clear_monthly_report_settings()

    response = auth_client.post(
        '/configuracion/monthly-report/update',
        data={
            'monthly_report_enabled': '1',
            'monthly_report_admin_only': '1',
            'monthly_report_admin_email': 'automatico@toscana.com',
        },
        follow_redirects=False,
    )

    with app.app_context():
        settings = get_monthly_report_settings(app.config)
        _clear_monthly_report_settings()

    assert response.status_code == 302
    assert settings['enabled'] is True
    assert settings['admin_only'] is True
    assert settings['admin_email'] == 'automatico@toscana.com'


@pytest.mark.integration
def test_monthly_report_send_route_dispatches_manual_send(auth_client, monkeypatch):
    captured = {}

    def fake_dispatch_monthly_financial_report(reference_dt=None,
                                               output_path=None,
                                               allow_retry_failed=True,
                                               period_mode='previous_month',
                                               app_config=None,
                                               admin_only=None,
                                               admin_email_override=None,
                                               respect_enabled_setting=False):
        captured['reference_dt'] = reference_dt
        captured['allow_retry_failed'] = allow_retry_failed
        captured['admin_only'] = admin_only
        captured['admin_email_override'] = admin_email_override
        captured['period_mode'] = period_mode
        captured['respect_enabled_setting'] = respect_enabled_setting
        return {
            'report_period': '2026-04',
            'sent': ['ana@example.com'],
            'skipped': ['admin@toscana.com'],
            'failed': [],
            'status': 'processed',
            'summary': {
                'message': 'Reporte 2026-04 enviado: 1 destinatarios enviados y 1 omitidos.',
                'detail': None,
                'category': 'success',
                'log_message': 'Reporte 2026-04 enviado: 1 destinatarios enviados y 1 omitidos.',
            },
        }

    monkeypatch.setattr(reports_module, 'dispatch_monthly_financial_report', fake_dispatch_monthly_financial_report)

    response = auth_client.post(
        '/reportes/mensual/send',
        data={
            'reference_date': '2026-04-12',
            'period_mode': 'current_month_to_date',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert 'reference_date=2026-04-12' in response.headers['Location']
    assert 'period_mode=current_month_to_date' in response.headers['Location']
    assert captured['reference_dt'].strftime('%Y-%m-%d') == '2026-04-12'
    assert captured['allow_retry_failed'] is True
    assert captured['admin_only'] is None
    assert captured['admin_email_override'] is None
    assert captured['period_mode'] == 'current_month_to_date'
    assert captured['respect_enabled_setting'] is False

    with auth_client.session_transaction() as session:
        flashes = session.get('_flashes', [])

    assert any(
        'Reporte 2026-04 enviado: 1 destinatarios enviados y 1 omitidos.' in message
        for category, message in flashes
    )


@pytest.mark.integration
def test_monthly_report_send_route_requires_admin(operator_client, monkeypatch):
    called = {'value': False}

    def fake_dispatch_monthly_financial_report(*args, **kwargs):
        called['value'] = True
        return {
            'report_period': '2026-04',
            'sent': ['ana@example.com'],
            'skipped': [],
            'failed': [],
        }

    monkeypatch.setattr(reports_module, 'dispatch_monthly_financial_report', fake_dispatch_monthly_financial_report)

    response = operator_client.post(
        '/reportes/mensual/send',
        data={
            'reference_date': '2026-04-12',
            'period_mode': 'current_month_to_date',
        },
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert called['value'] is False


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


@pytest.mark.integration
def test_scheduler_monthly_report_job_uses_shared_dispatch_service(app, monkeypatch):
    job = scheduler.get_job('send_monthly_financial_report')
    captured = {}

    def fake_dispatch_monthly_financial_report(reference_dt=None,
                                               output_path=None,
                                               allow_retry_failed=True,
                                               period_mode='previous_month',
                                               app_config=None,
                                               admin_only=None,
                                               admin_email_override=None,
                                               respect_enabled_setting=False):
        captured['reference_dt'] = reference_dt
        captured['output_path'] = output_path
        captured['allow_retry_failed'] = allow_retry_failed
        captured['period_mode'] = period_mode
        captured['app_config'] = app_config
        captured['admin_only'] = admin_only
        captured['admin_email_override'] = admin_email_override
        captured['respect_enabled_setting'] = respect_enabled_setting
        return {
            'report_period': '2026-04',
            'sent': ['ana@example.com'],
            'skipped': ['bruno@example.com'],
            'failed': [],
            'admin_only': True,
            'resolved_admin_email': 'automatico@toscana.com',
            'status': 'processed',
            'summary': {
                'message': 'Reporte 2026-04 enviado: 1 destinatarios enviados y 1 omitidos.',
                'detail': None,
                'category': 'success',
                'log_message': 'Reporte 2026-04 enviado: 1 destinatarios enviados y 1 omitidos.',
            },
        }

    monkeypatch.setattr(reports_module, 'dispatch_monthly_financial_report', fake_dispatch_monthly_financial_report)

    job.func()

    assert captured['app_config'] is app.config
    assert captured['respect_enabled_setting'] is True
    assert captured['allow_retry_failed'] is True
    assert captured['period_mode'] == 'previous_month'


@pytest.mark.unit
def test_send_monthly_report_cli_returns_error_when_dispatch_has_failures(monkeypatch):
    monkeypatch.setattr(monthly_report_cli, '_configure_stdout', lambda: None)
    monkeypatch.setattr(
        monthly_report_cli,
        '_run_dispatch_mode',
        lambda args: {
            'report_period': '2026-04',
            'sent': [],
            'skipped': [],
            'failed': [{'email': 'admin@toscana.com', 'error': 'SMTP error'}],
        },
    )
    monkeypatch.setattr(sys, 'argv', ['send_monthly_report.py', '--mode', 'dispatch'])

    exit_code = monthly_report_cli.main()

    assert exit_code == 1