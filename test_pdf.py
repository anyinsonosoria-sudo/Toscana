import os
import sys
from pathlib import Path

# Setup flask app context
from app import app
from data_models.models import Payment, Invoice
from extensions import db

with app.app_context():
    from blueprints.billing import view_receipt_pdf
    from flask import request
    
    payment = db.session.query(Payment).first()
    if payment:
        print(f"Testing view_receipt_pdf for payment {payment.id}")
        # We can't actually call view_receipt_pdf easily without a request context and logged in user
        # But we can test the inner logic
        import company
        import receipt_pdf
        
        invoice_num = payment.invoice_id
        invoice = payment.invoice
        apt_number = "1A"
        resident_name = "Test"
        safe_resident_name = "".join(c for c in resident_name if c.isalnum() or c in (' ', '_', '-')).strip()
        pdf_filename = f"Apartamento {apt_number}-{safe_resident_name}-Comprobante de pago Factura #{invoice_num}.pdf"
        
        pdf_dir = Path("static/invoices")
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = pdf_dir / pdf_filename
        
        print("pdf_filename:", pdf_filename)
        
        payment_data = {
            'id': payment.id,
            'amount': payment.amount,
            'method': payment.method,
            'payment_date': payment.paid_date[:10] if payment.paid_date else '2026-01-01',
            'notes': payment.notes or ''
        }
        
        invoice_data = {
            'id': invoice_num,
            'description': invoice.description,
            'amount': invoice.amount,
            'total_paid': payment.amount,
            'apartment_number': apt_number,
            'resident_name': resident_name,
            'resident_email': '',
            'resident_phone': ''
        }
        company_info = company.get_company_info() or {}
        
        print("Generating receipt PDF...")
        try:
            receipt_pdf.generate_payment_receipt_pdf(payment_data, invoice_data, company_info, str(pdf_path))
            print("Successfully generated receipt PDF at:", pdf_path)
            print("File exists:", pdf_path.exists())
            if pdf_path.exists():
                print("File size:", pdf_path.stat().st_size)
        except Exception as e:
            import traceback
            traceback.print_exc()
    else:
        print("No payment found")
