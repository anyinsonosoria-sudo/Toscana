from datetime import datetime, UTC

import apartments
import invoice_pdf
import models
import senders


def test_recurring_invoice_notification_still_sends_when_pdf_fails(app, monkeypatch):
    apartment_id = apartments.add_apartment(
        number=f"RI-{datetime.now(UTC).strftime('%H%M%S%f')}",
        resident_name="Cliente Prueba",
        resident_email="cliente@example.com",
        resident_phone="+18095550123",
    )

    sale_id = models.add_recurring_sale(
        unit_id=apartment_id,
        service_id=0,
        amount=1250.0,
        frequency='monthly',
        billing_day=1,
        start_date='2026-05-01',
        description='Servicio recurrente de prueba',
        active=True,
    )

    sent_notifications = []

    def fake_generate_invoice_pdf(*args, **kwargs):
        raise RuntimeError('pdf boom')

    def fake_send_invoice_notification(invoice, unit, client_email=None, admin_email=None,
                                       attach_pdf=False, pdf_path=None, client_phone=None):
        sent_notifications.append({
            'invoice': invoice,
            'unit': unit,
            'client_email': client_email,
            'admin_email': admin_email,
            'attach_pdf': attach_pdf,
            'pdf_path': pdf_path,
            'client_phone': client_phone,
        })

    monkeypatch.setattr(invoice_pdf, 'generate_invoice_pdf', fake_generate_invoice_pdf)
    monkeypatch.setattr(senders, 'send_invoice_notification', fake_send_invoice_notification)
    monkeypatch.setattr('company.get_company_info', lambda: {'email': 'admin@example.com'})

    invoice_id = models.generate_invoice_from_recurring(sale_id)

    assert invoice_id > 0
    assert len(sent_notifications) == 1
    notification = sent_notifications[0]
    assert notification['client_email'] == 'cliente@example.com'
    assert notification['admin_email'] == 'admin@example.com'
    assert notification['attach_pdf'] is False
    assert notification['pdf_path'] is None
    assert notification['client_phone'] == '+18095550123'