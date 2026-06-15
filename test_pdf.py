import sys
sys.path.append('.')
from extensions import db
from app import app
from db import get_conn
import apartments
import company
import receipt_pdf
from data_models.models import Invoice, Payment

with app.app_context():
    unit_id = 1
    apt = apartments.get_apartment(unit_id)
    if not apt:
        print("No apt found")
        sys.exit(1)
        
    invoices_orm = Invoice.query.filter_by(unit_id=unit_id).order_by(Invoice.issued_date.desc()).limit(20).all()
    invoices = [{
        'id': i.id, 'description': i.description, 'amount': i.amount,
        'issued_date': i.issued_date, 'due_date': i.due_date, 'paid': 1 if i.paid else 0
    } for i in invoices_orm]
    
    payments_orm = Payment.query.join(Invoice).filter(Invoice.unit_id == unit_id).order_by(Payment.paid_date.desc()).limit(20).all()
    payments = [{
        'id': p.id, 'amount': p.amount, 'paid_date': p.paid_date,
        'method': p.method, 'invoice_id': p.invoice_id
    } for p in payments_orm]
    
    company_info = company.get_company_info() or {}
    pdf_path = 'test_estado_cuenta.pdf'
    
    try:
        receipt_pdf.generate_account_statement_pdf(apt, invoices, payments, company_info, pdf_path)
        import os
        print(f'Generated PDF size: {os.path.getsize(pdf_path)} bytes')
    except Exception as e:
        import traceback
        traceback.print_exc()
