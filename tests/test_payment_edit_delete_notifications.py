"""Tests para edición y eliminación de pagos con notificación interna."""

import uuid

import pytest

import db
import senders
from blueprints import billing as billing_blueprint


def _create_payment_fixture():
    """Crea datos mínimos para probar edición y eliminación de pagos."""
    unique_id = uuid.uuid4().hex[:8]
    conn = db.get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO apartments(number, floor, resident_name, resident_email, resident_phone)
        VALUES(?, ?, ?, ?, ?)
        """,
        (f'TEST-{unique_id}', '1', 'Residente Test', 'residente@example.com', '8090000000'),
    )
    unit_id = cur.lastrowid

    cur.execute(
        """
        INSERT INTO invoices(unit_id, description, amount, issued_date, due_date, paid, pending_amount)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (unit_id, 'Mantenimiento mensual', 100.0, '2026-05-01', '2026-05-31', 0, 60.0),
    )
    invoice_id = cur.lastrowid

    cur.execute(
        """
        INSERT INTO payments(invoice_id, amount, paid_date, method, notes)
        VALUES(?, ?, ?, ?, ?)
        """,
        (invoice_id, 40.0, '2026-05-01 09:00:00', 'transferencia', 'Pago inicial'),
    )
    payment_id = cur.lastrowid

    cur.execute(
        """
        INSERT INTO accounting_transactions(type, description, amount, category, reference, date)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        ('income', 'Pago recibido: Mantenimiento mensual', 40.0, 'Ventas/Facturas', f'INV-{invoice_id}', '2026-05-01 09:00:00'),
    )

    conn.commit()
    conn.close()

    return {
        'unit_id': unit_id,
        'invoice_id': invoice_id,
        'payment_id': payment_id,
    }


@pytest.mark.integration
def test_update_payment_notifies_only_admin(auth_client, monkeypatch):
    fixture = _create_payment_fixture()
    captured = []

    monkeypatch.setattr(billing_blueprint, '_get_admin_email', lambda: 'admin@example.com')
    monkeypatch.setattr(
        senders,
        'send_payment_notification',
        lambda *args, **kwargs: pytest.fail('No debe enviarse correo al residente al editar un pago'),
    )

    def fake_send_payment_change_notification(action, payment, invoice, unit, admin_email=None, previous_payment=None):
        captured.append({
            'action': action,
            'payment': payment,
            'invoice': invoice,
            'unit': unit,
            'admin_email': admin_email,
            'previous_payment': previous_payment,
        })

    monkeypatch.setattr(senders, 'send_payment_change_notification', fake_send_payment_change_notification)

    response = auth_client.post(
        f"/ventas/pagos/edit/{fixture['payment_id']}",
        data={
            'amount': '55.00',
            'method': 'cheque',
            'paid_date': '2026-05-02T10:30',
            'notes': 'Pago ajustado',
            'next': '/ventas/registrar-pago',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/ventas/registrar-pago')

    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute('SELECT amount, method, notes, paid_date FROM payments WHERE id = ?', (fixture['payment_id'],))
    payment_row = cur.fetchone()
    assert payment_row is not None
    assert payment_row['amount'] == pytest.approx(55.0)
    assert payment_row['method'] == 'cheque'
    assert payment_row['notes'] == 'Pago ajustado'
    assert payment_row['paid_date'].startswith('2026-05-02 10:30')

    cur.execute('SELECT paid, pending_amount FROM invoices WHERE id = ?', (fixture['invoice_id'],))
    invoice_row = cur.fetchone()
    assert invoice_row is not None
    assert invoice_row['paid'] == 0
    assert invoice_row['pending_amount'] == pytest.approx(45.0)

    cur.execute(
        "SELECT amount FROM accounting_transactions WHERE reference = ? AND category = 'Ventas/Facturas' ORDER BY id",
        (f"INV-{fixture['invoice_id']}",),
    )
    accounting_rows = cur.fetchall()
    conn.close()

    assert len(accounting_rows) == 1
    assert accounting_rows[0]['amount'] == pytest.approx(55.0)

    assert len(captured) == 1
    assert captured[0]['action'] == 'edited'
    assert captured[0]['admin_email'] == 'admin@example.com'
    assert captured[0]['previous_payment']['amount'] == pytest.approx(40.0)
    assert captured[0]['payment']['amount'] == pytest.approx(55.0)


@pytest.mark.integration
def test_delete_payment_notifies_only_admin(auth_client, monkeypatch):
    fixture = _create_payment_fixture()
    captured = []

    monkeypatch.setattr(billing_blueprint, '_get_admin_email', lambda: 'admin@example.com')
    monkeypatch.setattr(
        senders,
        'send_payment_notification',
        lambda *args, **kwargs: pytest.fail('No debe enviarse correo al residente al eliminar un pago'),
    )

    def fake_send_payment_change_notification(action, payment, invoice, unit, admin_email=None, previous_payment=None):
        captured.append({
            'action': action,
            'payment': payment,
            'invoice': invoice,
            'unit': unit,
            'admin_email': admin_email,
            'previous_payment': previous_payment,
        })

    monkeypatch.setattr(senders, 'send_payment_change_notification', fake_send_payment_change_notification)

    response = auth_client.post(
        f"/ventas/pagos/delete/{fixture['payment_id']}",
        data={'next': '/ventas/registrar-pago'},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/ventas/registrar-pago')

    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id FROM payments WHERE id = ?', (fixture['payment_id'],))
    assert cur.fetchone() is None

    cur.execute('SELECT paid, pending_amount FROM invoices WHERE id = ?', (fixture['invoice_id'],))
    invoice_row = cur.fetchone()
    assert invoice_row is not None
    assert invoice_row['paid'] == 0
    assert invoice_row['pending_amount'] == pytest.approx(100.0)

    cur.execute(
        "SELECT COUNT(*) AS total FROM accounting_transactions WHERE reference = ? AND category = 'Ventas/Facturas'",
        (f"INV-{fixture['invoice_id']}",),
    )
    accounting_count = cur.fetchone()['total']
    conn.close()

    assert accounting_count == 0

    assert len(captured) == 1
    assert captured[0]['action'] == 'deleted'
    assert captured[0]['admin_email'] == 'admin@example.com'
    assert captured[0]['payment']['amount'] == pytest.approx(40.0)