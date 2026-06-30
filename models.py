"""
Models Module
=============
Funciones de acceso a datos para el sistema de facturación.
"""
import logging
import os
from typing import List, Dict, Optional

from extensions import db
from data_models.models import Invoice, Payment, RecurringSale, AccountingTransaction, Apartment, Resident
import db as legacy_db

logger = logging.getLogger(__name__)

# Intentar importar senders sin romper la importación del módulo
try:
    import senders  # type: ignore
    HAS_SENDERS = True
except Exception:
    HAS_SENDERS = False

# Intentar importar invoice_pdf
try:
    import invoice_pdf
    HAS_INVOICE_PDF = True
except Exception:
    HAS_INVOICE_PDF = False

# Importar config para verificar configuración
try:
    import config
    HAS_CONFIG = True
except Exception:
    HAS_CONFIG = False

from pathlib import Path
from datetime import datetime, UTC

LOG_PATH = Path(__file__).parent / "run.log"
NOTIFICATIONS_LOG_PATH = Path(__file__).parent / "notifications.log"


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace('+00:00', 'Z')


def _log(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{_utc_timestamp()} - {msg}\n")
    except Exception:
        pass

def _log_notification(msg: str):
    try:
        with open(NOTIFICATIONS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{_utc_timestamp()} - {msg}\n")
    except Exception:
        pass

def add_unit(number: str, owner: str, email: str = "", phone: str = "") -> int:
    """Agrega una unidad (legacy, usar apartments.add_apartment)"""
    try:
        with legacy_db.get_db() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO units(number, owner, email, phone) VALUES(?,?,?,?)",
                        (number, owner, email, phone))
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        _log(f"add_unit failed: {e}")
        raise

def list_units() -> List[Dict]:
    """Lista unidades (legacy)"""
    with legacy_db.get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, number, owner, email FROM units ORDER BY number")
        rows = cur.fetchall()
        return [dict(r) for r in rows]

def add_charge(unit_id: int, description: str, amount: float, due_date: Optional[str] = None) -> int:
    """Agrega un cargo"""
    with legacy_db.get_db() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO charges(unit_id, description, amount, due_date) VALUES(?,?,?,?)",
                    (unit_id, description, amount, due_date))
        conn.commit()
        return cur.lastrowid

def create_invoice(unit_id: int, description: str, amount: float, due_date: Optional[str] = None,
                   notify_email: Optional[str] = None, notify_phone: Optional[str] = None, 
                   recurring_sale_id: Optional[int] = None) -> int:
    # Validar monto positivo
    if amount <= 0:
        raise ValueError(f"El monto de la factura debe ser mayor a cero (recibido: {amount})")
    
    # 1. ORM Insert
    try:
        from datetime import datetime, timezone
        issued_date = datetime.now(timezone.utc).isoformat()
        new_inv = Invoice(
            unit_id=unit_id,
            description=description,
            amount=amount,
            due_date=due_date,
            recurring_sale_id=recurring_sale_id,
            issued_date=issued_date,
            paid=False,
            pending_amount=amount
        )
        db.session.add(new_inv)
        db.session.flush() # Para obtener el ID
        rid = new_inv.id
        
        # Obtener información adicional usando ORM
        apartment = db.session.get(Apartment, unit_id)
        resident = Resident.query.filter_by(unit_id=unit_id).first()
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        _log(f"create_invoice ORM insert failed: {e}")
        raise
        
    # 2. Dual-Write to legacy SQLite
    try:
        conn = legacy_db.get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO invoices
            (id, unit_id, description, amount, due_date, recurring_sale_id, issued_date, paid, pending_amount) 
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (rid, unit_id, description, amount, due_date, recurring_sale_id, issued_date, 0, amount))
        conn.commit()
        conn.close()
    except Exception as e:
        _log(f"create_invoice dual-write failed: {e}")

    # prepare dicts for PDF/email (similar to legacy output)
    inv_row = {
        'id': rid, 'unit_id': unit_id, 'description': description, 
        'amount': amount, 'due_date': due_date, 'issued_date': issued_date,
        'paid': 0, 'pending_amount': amount, 'recurring_sale_id': recurring_sale_id
    }
    
    invoice = inv_row
    unit = {
        'id': apartment.id if apartment else unit_id,
        'number': apartment.number if apartment else str(unit_id)
    }
    resident_dict = {
        'name': resident.name if resident else (apartment.resident_name if apartment else ''),
        'phone': resident.phone if resident else (apartment.resident_phone if apartment else ''),
        'email': resident.email if resident else (apartment.resident_email if apartment else '')
    }
    
    # Generate PDF if available
    pdf_filename = None
    if HAS_INVOICE_PDF:
        try:
            # Get company info
            from company import get_company_info
            from datetime import datetime as dt
            company_info = get_company_info()
            
            # Prepare invoice data for PDF
            invoice_data = {
                'id': invoice.get('id'),
                'description': invoice.get('description', ''),
                'notes': description,
                'amount': invoice.get('amount', 0),
                'issued_date': dt.fromisoformat(invoice.get('issued_date', dt.now().isoformat())).strftime('%B %d, %Y'),
                'due_date': dt.fromisoformat(invoice.get('due_date', dt.now().isoformat())).strftime('%B %d, %Y') if invoice.get('due_date') else 'N/A',
                'apartment_number': unit.get('number', ''),
                'resident_name': resident_dict.get('name', ''),
                'resident_phone': resident_dict.get('phone', ''),
                'resident_email': resident_dict.get('email', '')
            }
            
            # Create invoices directory
            invoices_dir = Path(__file__).parent / "static" / "invoices"
            invoices_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate PDF
            pdf_filename = f"invoice_{rid}.pdf"
            pdf_path = invoices_dir / pdf_filename
            invoice_pdf.generate_invoice_pdf(invoice_data, company_info, str(pdf_path))
            _log(f"PDF generated for invoice {rid}: {pdf_filename}")
        except Exception as e:
            _log(f"PDF generation failed for invoice {rid}: {e}")
            # Don't raise, PDF generation is not critical
    
    # send notifications if requested; log failures but do not raise
    # Siempre obtener admin_email para enviar copia
    admin_email = None
    try:
        from company import get_company_info
        ci = get_company_info()
        admin_email = ci.get('email') if ci else None
    except Exception:
        pass
    if not admin_email:
        admin_email = os.environ.get('SMTP_FROM') or os.environ.get('SMTP_USER')
    
    if notify_email or notify_phone or admin_email:
        if HAS_SENDERS:
            try:
                senders.send_invoice_notification(
                    invoice, 
                    unit, 
                    client_email=notify_email,
                    admin_email=admin_email,
                    client_phone=notify_phone,
                    attach_pdf=pdf_filename is not None,
                    pdf_path=str(Path(__file__).parent / 'static' / 'invoices' / pdf_filename) if pdf_filename else None
                )
            except Exception as e:
                try:
                    log_path = Path(__file__).parent / "notifications.log"
                    with open(log_path, "a", encoding="utf-8") as lf:
                        lf.write(f"{_utc_timestamp()} - Invoice {rid} notification failed: {e}\n")
                except Exception:
                    pass
                _log(f"create_invoice notification failed for {rid}: {e}")
                # Re-lanzar el error para que el usuario lo vea
                raise RuntimeError(f"Error al enviar notificación: {str(e)}")
        else:
            try:
                log_path = Path(__file__).parent / "notifications.log"
                with open(log_path, "a", encoding="utf-8") as lf:
                    lf.write(f"{_utc_timestamp()} - Invoice {rid} notification skipped: senders module not available\n")
            except Exception:
                pass
            _log(f"create_invoice notification skipped (senders missing) for {rid}")
    return rid

def list_invoices(unit_id: Optional[int] = None) -> List[Dict]:
    """Lista todas las facturas, opcionalmente filtradas por unidad"""
    query = Invoice.query
    if unit_id:
        query = query.filter_by(unit_id=unit_id)
    
    invoices = query.order_by(Invoice.id.desc()).all()
    
    # Return as dict for compatibility
    return [{
        'id': i.id,
        'unit_id': i.unit_id,
        'description': i.description,
        'amount': i.amount,
        'issued_date': i.issued_date,
        'due_date': i.due_date,
        'paid': 1 if i.paid else 0,
        'pending_amount': i.pending_amount,
        'recurring_sale_id': i.recurring_sale_id,
        'notes': i.notes
    } for i in invoices]

def get_invoice(invoice_id: int):
    """Obtiene una factura por su ID"""
    i = db.session.get(Invoice, invoice_id)
    if not i:
        return None
    return {
        'id': i.id,
        'unit_id': i.unit_id,
        'description': i.description,
        'amount': i.amount,
        'issued_date': i.issued_date,
        'due_date': i.due_date,
        'paid': 1 if i.paid else 0,
        'pending_amount': i.pending_amount,
        'recurring_sale_id': i.recurring_sale_id,
        'notes': i.notes
    }

# Alias para compatibilidad
get_invoice_by_id = get_invoice


def get_invoice_paid_amount(invoice_id: int) -> float:
    """
    Obtiene el total pagado de una factura.
    Retorna 0 si no hay pagos.
    """
    try:
        from sqlalchemy import func
        total = db.session.query(func.sum(Payment.amount)).filter(Payment.invoice_id == invoice_id).scalar()
        return float(total) if total else 0.0
    except Exception as e:
        logger.error(f"Error getting paid amount for invoice {invoice_id}: {e}")
        return 0.0


# ========== FUNCIONES AUXILIARES PARA PAGOS ==========

def _validate_payment(invoice_id: int, amount: float) -> Invoice:
    """
    Valida que el pago sea valido usando ORM.
    Retorna objeto Invoice si es valido, lanza excepcion si no.
    """
    if amount <= 0:
        raise ValueError(f"El monto del pago debe ser mayor a cero (recibido: {amount})")
    
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError(f"La factura #{invoice_id} no existe")
    
    # Calcular pagado total actual
    from sqlalchemy import func
    current_paid = db.session.query(func.sum(Payment.amount)).filter(Payment.invoice_id == invoice_id).scalar() or 0.0
    
    if current_paid + amount > invoice.amount:
        raise ValueError(
            f"El pago de RD$ {amount:,.2f} excede el saldo pendiente de RD$ {(invoice.amount - current_paid):,.2f}"
        )
    
    return invoice

def _insert_payment_record(invoice_id: int, amount: float, method: str, notes: str) -> Payment:
    """Inserta el registro de pago usando ORM. Retorna objeto Payment."""
    from datetime import datetime, timezone
    p = Payment(
        invoice_id=invoice_id,
        amount=amount,
        method=method,
        notes=notes,
        paid_date=datetime.now(timezone.utc).isoformat()
    )
    db.session.add(p)
    db.session.flush() # obtener ID
    return p

def _update_invoice_status(invoice: Invoice) -> float:
    """
    Actualiza el estado de la factura basado en pagos totales.
    Retorna el total pagado.
    """
    from sqlalchemy import func
    total_paid = db.session.query(func.sum(Payment.amount)).filter(Payment.invoice_id == invoice.id).scalar() or 0.0
    
    pending_amount = max(invoice.amount - total_paid, 0)
    is_paid = total_paid >= invoice.amount
    
    invoice.paid = is_paid
    invoice.pending_amount = pending_amount
    db.session.flush()
    return float(total_paid)

def _create_accounting_entry(invoice_id: int, amount: float, description: str) -> AccountingTransaction:
    """Crea entrada contable para el pago usando ORM."""
    from datetime import datetime
    payment_date = datetime.now().strftime("%Y-%m-%d")
    
    txn = AccountingTransaction(
        type='income',
        description=f'Pago recibido: {description}',
        amount=amount,
        category='Ventas/Facturas',
        reference=f'INV-{invoice_id}',
        date=payment_date
    )
    db.session.add(txn)
    db.session.flush()
    return txn

def _generate_account_statement_pdf(apt: Dict, invoice_dict: Dict) -> Optional[str]:
    """
    Genera PDF del estado de cuenta.
    Retorna la ruta del archivo o None si falla.
    """
    try:
        from pathlib import Path
        import os
        
        # Obtener todas las facturas y pagos del apartamento
        unit_id = apt.get('id')
        
        # ORM Queries
        invoices_orm = Invoice.query.filter_by(unit_id=unit_id).order_by(Invoice.issued_date.desc()).limit(10).all()
        invoices = [{
            'id': i.id, 'description': i.description, 'amount': i.amount, 
            'issued_date': i.issued_date, 'due_date': i.due_date, 'paid': 1 if i.paid else 0
        } for i in invoices_orm]
        
        payments_orm = Payment.query.join(Invoice).filter(Invoice.unit_id == unit_id).order_by(Payment.paid_date.desc()).limit(10).all()
        payments = [{
            'id': p.id, 'amount': p.amount, 'paid_date': p.paid_date, 
            'method': p.method, 'invoice_id': p.invoice_id
        } for p in payments_orm]
        
        # Calcular balance
        balance = get_balance(unit_id)
        
        # Crear directorio
        statement_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "static" / "invoices"
        statement_dir.mkdir(parents=True, exist_ok=True)
        
        # Nombre formato: Apartamento 4A-Anyinson Osoria-Estado de cuenta
        apt_number = apt.get('number', 'N/A')
        resident_name = apt.get('resident_name', 'Cliente')
        statement_filename = f"Apartamento {apt_number}-{resident_name}-Estado de cuenta.pdf"
        statement_path = str(statement_dir / statement_filename)
        
        # Generar PDF del estado de cuenta
        from receipt_pdf import generate_account_statement_pdf
        import company
        
        company_info = company.get_company_info() or {}
        generate_account_statement_pdf(apt, invoices, payments, company_info, statement_path)
        
        _log(f"Account statement generated: {statement_path}")
        return statement_path
        
    except Exception as e:
        _log(f"Error generating account statement: {e}")
        return None


def _generate_receipt_pdf(payment_id: int, invoice_id: int, amount: float, 
                          method: str, total_paid: float, notes: str = "") -> Optional[str]:
    """
    Genera PDF del recibo de pago.
    Retorna la ruta del archivo o None si falla.
    """
    if not HAS_INVOICE_PDF:
        return None
    
    try:
        from datetime import datetime as dt_now
        import receipt_pdf
        import company
        from apartments import get_apartment
        from pathlib import Path
        import os
        
        # Obtener datos necesarios
        company_info = company.get_company_info() or {}
        invoice = get_invoice(invoice_id)
        
        if not invoice:
            return None
        
        apt = get_apartment(invoice['unit_id'])
        
        # Preparar datos
        payment_data = {
            'id': payment_id,
            'amount': amount,
            'method': method,
            'payment_date': dt_now.now().strftime('%B %d, %Y'),
            'notes': notes
        }
        
        invoice_data = {
            'id': invoice_id,
            'description': invoice['description'],
            'amount': invoice['amount'],
            'total_paid': total_paid,
            'apartment_number': apt.get('number', '') if apt else '',
            'resident_name': apt.get('resident_name', '') if apt else '',
            'resident_email': apt.get('resident_email', '') if apt else '',
            'resident_phone': apt.get('resident_phone', '') if apt else ''
        }
        
        # Crear directorio y generar PDF
        receipt_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "static" / "invoices"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        
        # Nombre formato: Apartamento 4A-Anyinson Osoria-Comprobante de pago Factura #2
        apt_number = invoice_data.get('apartment_number', 'N/A')
        resident_name = invoice_data.get('resident_name', 'Cliente')
        invoice_num = invoice_data.get('id', payment_id)
        receipt_filename = f"Apartamento {apt_number}-{resident_name}-Comprobante de pago Factura #{invoice_num}.pdf"
        receipt_path = str(receipt_dir / receipt_filename)
        receipt_pdf.generate_payment_receipt_pdf(payment_data, invoice_data, company_info, receipt_path)
        
        _log(f"Payment receipt generated: {receipt_path}")
        return receipt_path
        
    except Exception as e:
        _log(f"Error generating payment receipt: {e}")
        return None


def _get_client_contact_info(invoice: Dict) -> Dict:
    """
    Obtiene informacion de contacto del cliente.
    Retorna dict con email y phone.
    """
    from apartments import get_apartment
    
    apt = get_apartment(invoice.get('unit_id'))
    
    client_email = apt.get('resident_email').strip() if apt and apt.get('resident_email') else None
    client_phone = apt.get('resident_phone').strip() if apt and apt.get('resident_phone') else None
    
    # Si no hay email en apartments, buscar en residents
    if not client_email and apt and apt.get('id'):
        try:
            with legacy_db.get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT email FROM residents WHERE unit_id=? LIMIT 1", (apt['id'],))
                res_row = cur.fetchone()
                if res_row and res_row['email']:
                    client_email = res_row['email'].strip()
        except Exception as e:
            _log(f"Error buscando email en residents: {e}")
    
    return {
        'email': client_email,
        'phone': client_phone,
        'apartment': apt
    }


def _send_payment_notifications(payment_id: int, invoice: Dict, amount: float, 
                                 method: str, receipt_path: Optional[str], 
                                 statement_path: Optional[str] = None) -> None:
    """Envia notificaciones de pago por email y WhatsApp."""
    if not HAS_SENDERS:
        return
    
    try:
        from datetime import datetime as dt_now
        import company
        import re
        
        company_info = company.get_company_info() or {}
        contact_info = _get_client_contact_info(invoice)
        
        client_email = contact_info['email']
        client_phone = contact_info['phone']
        admin_email = company_info.get('email')
        # Fallback: usar SMTP_FROM como admin email
        if not admin_email:
            admin_email = os.environ.get('SMTP_FROM') or os.environ.get('SMTP_USER')
        apt = contact_info['apartment']
        
        if not (client_email or admin_email or client_phone):
            return
        
        # Preparar datos
        payment_dict = {
            'id': payment_id,
            'amount': amount,
            'method': method,
            'payment_date': dt_now.now().strftime('%B %d, %Y')
        }
        
        unit_dict = {
            'id': apt.get('id') if apt else None,
            'number': apt.get('number') if apt else 'N/A'
        }
        
        # Enviar notificaciones
        senders.send_payment_notification(
            payment_dict,
            invoice,
            unit_dict,
            client_email=client_email,
            admin_email=admin_email,
            receipt_path=receipt_path,
            account_statement_path=statement_path,
            client_phone=client_phone
        )
        
        # Validar y mostrar warnings si es necesario
        def is_valid_email(email):
            if not email or not isinstance(email, str):
                return False
            return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()) is not None
        
        try:
            from flask import has_request_context, flash
            if has_request_context():
                if not client_email:
                    flash("No se proporciono correo electronico del cliente.", "warning")
                elif not is_valid_email(client_email):
                    flash(f"El correo del cliente es invalido: {client_email}", "warning")
        except Exception:
            pass
        
        _log(f"Payment notifications sent for payment {payment_id}")
        
    except Exception as e:
        _log(f"Error sending payment notifications: {e}")
        try:
            from flask import has_request_context, flash
            if has_request_context():
                flash(f"Error enviando comprobante: {e}", "error")
        except Exception:
            pass


def record_payment(invoice_id: int, amount: float, method: str = "unknown", 
                   generate_receipt: bool = True, send_notifications: bool = True, notes: str = "") -> int:
    """
    Registra un pago y opcionalmente genera recibo PDF y envia notificaciones.
    """
    payment_id = None
    total_paid = 0
    invoice_dict = None
    
    # Fase 1: Operaciones ORM
    try:
        # Validar pago
        invoice_orm = _validate_payment(invoice_id, amount)
        description = invoice_orm.description or f'Pago de Factura #{invoice_id}'
        
        # Insertar pago
        payment_orm = _insert_payment_record(invoice_id, amount, method, notes)
        payment_id = payment_orm.id
        
        # Actualizar estado de factura
        total_paid = _update_invoice_status(invoice_orm)
        
        # Crear entrada contable
        txn_orm = _create_accounting_entry(invoice_id, amount, description)
        txn_id = txn_orm.id
        
        db.session.commit()
        _log(f"Payment {payment_id} recorded: ${amount} for invoice {invoice_id}")
        
    except Exception as e:
        db.session.rollback()
        _log(f"Error recording payment for invoice {invoice_id}: {e}")
        raise
        
    # Fase 1.5: Dual-Write
    try:
        conn = legacy_db.get_conn()
        cur = conn.cursor()
        
        # 1. Update Invoices
        inv = db.session.get(Invoice, invoice_id)
        cur.execute("UPDATE invoices SET paid=?, pending_amount=? WHERE id=?", 
                   (1 if inv.paid else 0, inv.pending_amount, inv.id))
                   
        # 2. Insert Payment
        p = db.session.get(Payment, payment_id)
        cur.execute("INSERT OR IGNORE INTO payments(id, invoice_id, amount, method, notes, paid_date) VALUES(?,?,?,?,?,?)",
                   (p.id, p.invoice_id, p.amount, p.method, p.notes, p.paid_date))
                   
        # 3. Insert Txn
        t = db.session.get(AccountingTransaction, txn_id)
        cur.execute("INSERT OR IGNORE INTO accounting_transactions(id, type, description, amount, category, reference, date) VALUES(?,?,?,?,?,?,?)",
                   (t.id, t.type, t.description, t.amount, t.category, t.reference, t.date))
                   
        conn.commit()
        conn.close()
    except Exception as e:
        _log(f"Dual-write failed for record_payment {payment_id}: {e}")

    # Fase 2: Operaciones externas
    receipt_path = None
    
    if generate_receipt:
        receipt_path = _generate_receipt_pdf(payment_id, invoice_id, amount, method, total_paid, notes)
    
    if send_notifications:
        invoice = get_invoice(invoice_id)
        if invoice:
            statement_path = None
            try:
                from apartments import get_apartment
                apt = get_apartment(invoice.get('unit_id'))
                if apt:
                    statement_path = _generate_account_statement_pdf(apt, invoice)
            except Exception as e:
                _log(f"Error generating account statement: {e}")
            
            _send_payment_notifications(payment_id, invoice, amount, method, receipt_path, statement_path)
    
    return payment_id

def get_balance(unit_id: int) -> float:
    """Calcula el balance pendiente de una unidad"""
    from sqlalchemy import func
    total_invoiced = db.session.query(func.sum(Invoice.amount)).filter(Invoice.unit_id == unit_id).scalar() or 0.0
    
    total_paid = db.session.query(func.sum(Payment.amount)).join(Invoice).filter(Invoice.unit_id == unit_id).scalar() or 0.0
    
    return float(total_invoiced) - float(total_paid)


# ========== VENTAS RECURRENTES ==========

def create_recurring_sales_table():
    """Crear tabla de ventas recurrentes si no existe"""
    conn = legacy_db.get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recurring_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER NOT NULL,
            service_id INTEGER,
            amount REAL NOT NULL,
            frequency TEXT NOT NULL,
            billing_day INTEGER DEFAULT 1,
            billing_time TEXT DEFAULT '08:00',
            start_date TEXT NOT NULL,
            end_date TEXT,
            description TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (unit_id) REFERENCES apartments(id) ON DELETE CASCADE
        )
    """)
    # Ensure billing_time column exists for existing databases
    try:
        cur.execute("ALTER TABLE recurring_sales ADD COLUMN billing_time TEXT DEFAULT '08:00'")
        conn.commit()
    except Exception:
        pass  # Column already exists
    # Ensure end_date column exists for existing databases
    try:
        cur.execute("ALTER TABLE recurring_sales ADD COLUMN end_date TEXT")
        conn.commit()
    except Exception:
        pass  # Column already exists
    conn.commit()
    conn.close()

def add_recurring_sale(unit_id: int, service_id: int, amount: float, frequency: str,
                       billing_day: int, start_date: str, description: str = "", active: bool = True) -> int:
    """Crear una venta recurrente usando ORM + Dual-Write"""
    if amount <= 0:
        raise ValueError(f"El monto de la venta recurrente debe ser mayor a cero (recibido: {amount})")
    
    try:
        from data_models.models import RecurringSale

        import db as legacy_db
        from datetime import datetime, timezone
        
        # ORM Insert
        rs = RecurringSale(
            unit_id=unit_id,
            service_id=service_id,
            amount=amount,
            frequency=frequency,
            billing_day=billing_day,
            start_date=start_date,
            description=description,
            active=bool(active),
            created_at=datetime.now(timezone.utc).isoformat(),
            billing_time='08:00'
        )
        db.session.add(rs)
        db.session.commit()
        
        sale_id = rs.id
        
        # Dual-Write
        try:
            conn = legacy_db.get_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT OR IGNORE INTO recurring_sales (id, unit_id, service_id, amount, frequency, billing_day, 
                                             start_date, description, active, billing_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (rs.id, rs.unit_id, rs.service_id, rs.amount, rs.frequency, rs.billing_day, rs.start_date, 
                  rs.description, 1 if rs.active else 0, rs.billing_time, rs.created_at))
            conn.commit()
            conn.close()
        except Exception as e:
            _log(f"Dual write failed for add_recurring_sale: {e}")
            
        return sale_id
    except Exception as e:
        db.session.rollback()
        raise e

def list_recurring_sales() -> List[Dict]:
    """Listar todas las ventas recurrentes con info de apartamento y servicio"""
    conn = legacy_db.get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT rs.*,
               a.number   AS apt_number,
               a.resident_name,
               a.resident_email,
               ps.name    AS service_name
        FROM recurring_sales rs
        LEFT JOIN apartments a ON rs.unit_id = a.id
        LEFT JOIN products_services ps ON rs.service_id = ps.id
        ORDER BY rs.active DESC, rs.id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def toggle_recurring_sale(sale_id: int) -> bool:
    """Activar/desactivar una venta recurrente (ORM + Dual-Write)"""
    from data_models.models import RecurringSale

    import db as legacy_db
    
    rs = db.session.get(RecurringSale, sale_id)
    if not rs:
        return False
        
    rs.active = not rs.active
    db.session.commit()
    
    try:
        conn = legacy_db.get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE recurring_sales SET active = ? WHERE id = ?", (1 if rs.active else 0, sale_id))
        conn.commit()
        conn.close()
    except Exception as e:
        _log(f"Dual write failed for toggle_recurring_sale: {e}")
        
    return True

def duplicate_recurring_sale(sale_id: int) -> int:
    """Duplicar una venta recurrente"""
    from data_models.models import RecurringSale

    import db as legacy_db
    
    rs = db.session.get(RecurringSale, sale_id)
    if not rs:
        raise Exception(f"Venta recurrente #{sale_id} no encontrada")
        
    from datetime import datetime, timezone
    new_rs = RecurringSale(
        unit_id=rs.unit_id,
        service_id=rs.service_id,
        amount=rs.amount,
        frequency=rs.frequency,
        billing_day=rs.billing_day,
        billing_time=rs.billing_time,
        start_date=rs.start_date,
        end_date=rs.end_date,
        description=(rs.description or "") + " (Copia)",
        active=rs.active,
        created_at=datetime.now(timezone.utc).isoformat()
    )
    db.session.add(new_rs)
    db.session.commit()
    
    new_id = new_rs.id
    
    try:
        conn = legacy_db.get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO recurring_sales (id, unit_id, service_id, amount, frequency, billing_day, 
                billing_time, start_date, end_date, description, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (new_rs.id, new_rs.unit_id, new_rs.service_id, new_rs.amount, new_rs.frequency, new_rs.billing_day,
              new_rs.billing_time, new_rs.start_date, new_rs.end_date, new_rs.description, 
              1 if new_rs.active else 0, new_rs.created_at))
        conn.commit()
        conn.close()
    except Exception as e:
        _log(f"Dual write failed for duplicate_recurring_sale: {e}")
        
    _log(f"Venta recurrente {sale_id} duplicada como {new_id}")
    return new_id


def update_recurring_sale(sale_id: int, **fields) -> None:
    """Actualizar una venta recurrente existente (ORM + Dual Write)"""
    if not fields:
        return
        
    from data_models.models import RecurringSale

    import db as legacy_db
    
    rs = db.session.get(RecurringSale, sale_id)
    if not rs:
        return
        
    ALLOWED = {'unit_id', 'service_id', 'amount', 'frequency', 'billing_day',
               'billing_time', 'start_date', 'end_date', 'description', 'active'}
               
    for k, v in fields.items():
        if k in ALLOWED:
            if k == 'active':
                setattr(rs, k, bool(v))
            else:
                setattr(rs, k, v)
                
    db.session.commit()
    
    # Dual-Write
    try:
        keys = []
        vals = []
        for k, v in fields.items():
            if k not in ALLOWED:
                continue
            keys.append(f"{k}=?")
            vals.append(v)
            
        if keys:
            vals.append(sale_id)
            conn = legacy_db.get_conn()
            cur = conn.cursor()
            cur.execute(f"UPDATE recurring_sales SET {', '.join(keys)} WHERE id=?", vals)
            conn.commit()
            conn.close()
    except Exception as e:
        _log(f"Dual write failed for update_recurring_sale: {e}")
        
    _log(f"Venta recurrente {sale_id} actualizada: {list(fields.keys())}")


def get_recurring_sale(sale_id: int) -> Optional[Dict]:
    """Obtener una venta recurrente por ID"""
    conn = legacy_db.get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT rs.*, a.number AS apt_number, a.resident_name, ps.name AS service_name
        FROM recurring_sales rs
        LEFT JOIN apartments a ON rs.unit_id = a.id
        LEFT JOIN products_services ps ON rs.service_id = ps.id
        WHERE rs.id = ?
    """, (sale_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_last_invoice_from_recurring(sale_id: int) -> int:
    """Obtener el ID de la última factura generada de una venta recurrente
    
    Args:
        sale_id: ID de la venta recurrente
        
    Returns:
        ID de la última factura o None si no hay facturas
    """
    conn = legacy_db.get_conn()
    cur = conn.cursor()
    
    # Buscar facturas por recurring_sale_id (preferido)
    cur.execute("""
        SELECT id FROM invoices 
        WHERE recurring_sale_id = ?
        ORDER BY issued_date DESC, id DESC
        LIMIT 1
    """, (sale_id,))
    
    invoice_row = cur.fetchone()
    
    # Fallback: buscar por unit_id y descripción si no hay recurring_sale_id
    if not invoice_row:
        cur.execute("SELECT unit_id, description FROM recurring_sales WHERE id = ?", (sale_id,))
        sale_row = cur.fetchone()
        if sale_row:
            sale = dict(sale_row)
            cur.execute("""
                SELECT id FROM invoices 
                WHERE unit_id = ? AND description LIKE ?
                ORDER BY issued_date DESC, id DESC
                LIMIT 1
            """, (sale['unit_id'], f"%{sale['description']}%"))
            invoice_row = cur.fetchone()
    
    conn.close()
    
    return invoice_row['id'] if invoice_row else None


def delete_recurring_sale(sale_id: int, confirmed: bool = False) -> Dict:
    """Eliminar una venta recurrente y todas sus facturas asociadas (ORM + Dual Write)"""
    from data_models.models import RecurringSale, Invoice, Payment, AccountingTransaction

    import db as legacy_db
    from sqlalchemy import func
    
    rs = db.session.get(RecurringSale, sale_id)
    if not rs:
        return {'requires_confirmation': False, 'deleted': False}
        
    invoices = Invoice.query.filter_by(recurring_sale_id=sale_id).all()
    invoice_ids = [i.id for i in invoices]
    paid_invoices = [i for i in invoices if i.paid]
    total_paid_amount = sum(i.amount for i in paid_invoices)
    
    result = {
        'requires_confirmation': False,
        'invoice_count': len(invoice_ids),
        'paid_invoice_count': len(paid_invoices),
        'total_amount': total_paid_amount,
        'deleted': False
    }
    
    if len(paid_invoices) > 0 and not confirmed:
        return result
        
    # Eliminar PDF files
    from pathlib import Path
    for invoice_id in invoice_ids:
        try:
            pdf_path = Path(__file__).parent / "static" / "invoices" / f"invoice_{invoice_id}.pdf"
            if pdf_path.exists():
                pdf_path.unlink()
                _log(f"PDF eliminado: invoice_{invoice_id}.pdf")
        except Exception as e:
            _log(f"Error eliminando PDF de factura {invoice_id}: {e}")
            
    # Eliminar Payments y Accounting Transactions para cada factura
    for invoice_id in invoice_ids:
        Payment.query.filter_by(invoice_id=invoice_id).delete()
        AccountingTransaction.query.filter_by(reference=f'INV-{invoice_id}').delete()
        
    # Eliminar Invoices
    Invoice.query.filter_by(recurring_sale_id=sale_id).delete()
    
    # Eliminar RecurringSale
    db.session.delete(rs)
    db.session.commit()
    
    # Dual-Write
    try:
        conn = legacy_db.get_conn()
        cur = conn.cursor()
        for invoice_id in invoice_ids:
            cur.execute("DELETE FROM payments WHERE invoice_id = ?", (invoice_id,))
            cur.execute("DELETE FROM accounting_transactions WHERE reference = ?", (f'INV-{invoice_id}',))
        cur.execute("DELETE FROM invoices WHERE recurring_sale_id = ?", (sale_id,))
        cur.execute("DELETE FROM recurring_sales WHERE id = ?", (sale_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        _log(f"Dual write failed for delete_recurring_sale: {e}")
        
    _log(f"Venta recurrente {sale_id} eliminada con {len(invoice_ids)} facturas asociadas")
    result['deleted'] = True
    return result


def process_due_recurring_invoices() -> dict:
    """Procesar todas las facturas recurrentes que deben generarse hoy.

    Revisa cada venta recurrente activa y genera una factura cuando:
    - Se ha alcanzado (o superado) el `billing_day` del ciclo actual.
    - Se ha alcanzado (o superado) el `billing_time` configurado (HH:MM).
    - No existe ya una factura para ese ciclo.
    - La venta está dentro de su rango start_date / end_date.

    Returns:
        Dict con listas 'generated' (sale_id, invoice_id), 'skipped' y 'errors'.
    """
    from datetime import datetime, timedelta

    result: dict = {'generated': [], 'skipped': [], 'errors': []}
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    current_time_str = now.strftime('%H:%M')  # e.g. '13:47'

    conn = legacy_db.get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM recurring_sales
        WHERE active = 1
          AND (start_date IS NULL OR start_date <= ?)
          AND (end_date   IS NULL OR end_date   >= ?)
    """, (today_str, today_str))
    sales = [dict(r) for r in cur.fetchall()]
    conn.close()

    for sale in sales:
        sale_id   = sale['id']
        frequency = sale.get('frequency', 'monthly')
        billing_day = int(sale.get('billing_day') or 1)
        billing_time = (sale.get('billing_time') or '00:00').strip()[:5]  # 'HH:MM'
        last_generated = sale.get('last_generated')  # YYYY-MM-DD or None

        # ── Verificar que ya se alcanzó la hora programada hoy ──
        if current_time_str < billing_time:
            result['skipped'].append(sale_id)
            continue

        try:
            should_generate = False

            if frequency == 'monthly':
                # Generar si hoy >= billing_day y sin factura este mes
                if now.day >= billing_day:
                    cycle_start = now.strftime('%Y-%m-01')
                    conn2 = legacy_db.get_conn()
                    c2 = conn2.cursor()
                    c2.execute("""
                        SELECT id FROM invoices
                        WHERE recurring_sale_id = ? AND issued_date >= ?
                        LIMIT 1
                    """, (sale_id, cycle_start))
                    should_generate = c2.fetchone() is None
                    conn2.close()

            elif frequency == 'weekly':
                if last_generated:
                    last_dt = datetime.strptime(last_generated, '%Y-%m-%d')
                    should_generate = (now - last_dt).days >= 7
                else:
                    should_generate = True

            elif frequency in ('biweekly', 'quincenal', 'bimonthly'):
                if last_generated:
                    last_dt = datetime.strptime(last_generated, '%Y-%m-%d')
                    should_generate = (now - last_dt).days >= 14
                else:
                    should_generate = True

            elif frequency == 'yearly':
                # Generar si hoy >= billing_day, mismo mes que start_date, sin factura este año
                if now.day >= billing_day:
                    start_date_str = sale.get('start_date', '')
                    try:
                        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                        if now.month == start_dt.month:
                            year_start = now.strftime('%Y-01-01')
                            conn2 = legacy_db.get_conn()
                            c2 = conn2.cursor()
                            c2.execute("""
                                SELECT id FROM invoices
                                WHERE recurring_sale_id = ? AND issued_date >= ?
                                LIMIT 1
                            """, (sale_id, year_start))
                            should_generate = c2.fetchone() is None
                            conn2.close()
                    except Exception:
                        pass
            else:
                # Frecuencia desconocida: tratar como mensual
                if now.day >= billing_day:
                    cycle_start = now.strftime('%Y-%m-01')
                    conn2 = legacy_db.get_conn()
                    c2 = conn2.cursor()
                    c2.execute("""
                        SELECT id FROM invoices
                        WHERE recurring_sale_id = ? AND issued_date >= ?
                        LIMIT 1
                    """, (sale_id, cycle_start))
                    should_generate = c2.fetchone() is None
                    conn2.close()

            if should_generate:
                invoice_id = generate_invoice_from_recurring(sale_id)
                result['generated'].append({'sale_id': sale_id, 'invoice_id': invoice_id})
                _log(f"[Scheduler] Factura automática generada: venta #{sale_id} -> factura #{invoice_id}")
            else:
                result['skipped'].append(sale_id)

        except Exception as e:
            msg = f"Venta #{sale_id}: {e}"
            result['errors'].append(msg)
            _log(f"[Scheduler] Error procesando venta recurrente #{sale_id}: {e}")

    summary = (f"[Scheduler] Facturas recurrentes procesadas: "
               f"{len(result['generated'])} generadas, "
               f"{len(result['skipped'])} omitidas, "
               f"{len(result['errors'])} errores")
    _log(summary)
    print(summary)
    return result


def _notify_recurring_invoice(invoice_id: int,
                              sale: Dict,
                              apartment: Dict,
                              service_name: str,
                              issued_date: str,
                              due_date: str) -> None:
    """Enviar notificacion de factura recurrente sin depender del PDF."""
    company_info: Dict = {}
    try:
        from company import get_company_info
        company_info = get_company_info() or {}
    except Exception as exc:
        _log(f"Recurring invoice {invoice_id} company info lookup failed: {exc}")

    service_code = 'N/A'
    additional_notes = ''
    if sale.get('service_id'):
        try:
            import products_services
            service = products_services.get_product_service(sale['service_id'])
            if service:
                service_code = service.get('code', 'N/A')
                additional_notes = service.get('additional_notes', '')
        except Exception as exc:
            _log(f"Error obteniendo detalles del producto/servicio {sale['service_id']}: {exc}")

    pdf_path = None
    if HAS_INVOICE_PDF:
        try:
            pdf_dir = Path(__file__).parent / "static" / "invoices"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = str(pdf_dir / f"invoice_{invoice_id}.pdf")

            invoice_data = {
                'id': invoice_id,
                'description': service_name,
                'amount': sale['amount'],
                'issued_date': issued_date,
                'due_date': due_date,
                'apartment_number': apartment.get('number', ''),
                'resident_name': apartment.get('resident_name', ''),
                'resident_email': apartment.get('resident_email', ''),
                'resident_phone': apartment.get('resident_phone', ''),
                'service_code': service_code,
                'notes': additional_notes,
            }
            invoice_pdf.generate_invoice_pdf(invoice_data, company_info, pdf_path)
        except Exception as exc:
            pdf_path = None
            _log(f"Recurring invoice {invoice_id} PDF generation failed: {exc}")
            _log_notification(f"Recurring invoice {invoice_id} PDF generation failed: {exc}")

    notify_email = apartment.get('resident_email')
    notify_phone = apartment.get('resident_phone')
    admin_email = company_info.get('email') if company_info else None
    if not admin_email:
        admin_email = os.environ.get('SMTP_FROM') or os.environ.get('SMTP_USER')

    if not (notify_email or admin_email or notify_phone):
        _log(
            f"Recurring invoice {invoice_id} notification skipped: no client/admin email or phone configured"
        )
        return

    if not HAS_SENDERS:
        message = f"Recurring invoice {invoice_id} notification skipped: senders module not available"
        _log(message)
        _log_notification(message)
        return

    invoice_dict = {
        'id': invoice_id,
        'amount': sale['amount'],
        'description': service_name,
        'issued_date': issued_date,
        'due_date': due_date,
        'resident_name': apartment.get('resident_name', ''),
    }
    unit_dict = {
        'id': apartment.get('id'),
        'number': apartment.get('number', ''),
        'resident_name': apartment.get('resident_name', ''),
    }

    try:
        senders.send_invoice_notification(
            invoice_dict,
            unit_dict,
            client_email=notify_email,
            admin_email=admin_email,
            attach_pdf=bool(pdf_path),
            pdf_path=pdf_path,
            client_phone=notify_phone,
        )
        recipients = []
        if notify_email:
            recipients.append(notify_email)
        if admin_email:
            recipients.append(admin_email)
        if recipients:
            _log(
                f"Recurring invoice {invoice_id} notification sent to: {', '.join(recipients)}"
            )
    except Exception as exc:
        message = f"Recurring invoice {invoice_id} notification failed: {exc}"
        _log(message)
        _log_notification(message)


def generate_invoice_from_recurring(sale_id: int) -> int:
    """Generar una factura desde una venta recurrente"""
    conn = legacy_db.get_conn()
    cur = conn.cursor()

    # Obtener datos de la venta recurrente
    cur.execute("SELECT * FROM recurring_sales WHERE id = ?", (sale_id,))
    sale_row = cur.fetchone()
    
    if not sale_row:
        conn.close()
        raise Exception(f"Venta recurrente #{sale_id} no encontrada")
    
    sale = dict(sale_row)

    if not sale['active']:
        conn.close()
        raise Exception("La venta recurrente está inactiva")

    # Obtener datos del apartamento (con residente)
    import apartments
    apartment = apartments.get_apartment(sale['unit_id'])
    
    if not apartment:
        conn.close()
        raise Exception(f"Apartamento #{sale['unit_id']} no encontrado")
    
    # Validar que tenga datos del residente (email es opcional)
    # if not apartment.get('resident_email'):
    #     conn.close()
    #     raise Exception(f"El apartamento #{apartment.get('number', sale['unit_id'])} no tiene email registrado")
    
    unit_id = apartment['id']
    
    # Verificar duplicado según la frecuencia configurada
    from datetime import datetime, timedelta
    now = datetime.now()
    frequency = sale.get('frequency', 'monthly')
    if frequency == 'weekly':
        cycle_start = (now - timedelta(days=6)).strftime('%Y-%m-%d')
        cycle_label = 'esta semana'
    elif frequency in ('biweekly', 'quincenal', 'bimonthly'):
        cycle_start = (now - timedelta(days=13)).strftime('%Y-%m-%d')
        cycle_label = 'en los últimos 14 días'
    elif frequency == 'yearly':
        cycle_start = now.strftime('%Y-01-01')
        cycle_label = 'este año'
    else:  # monthly (default)
        cycle_start = now.strftime('%Y-%m-01')
        cycle_label = 'este mes'
    cur.execute("""
        SELECT id FROM invoices
        WHERE recurring_sale_id = ? AND issued_date >= ?
        LIMIT 1
    """, (sale_id, cycle_start))
    existing = cur.fetchone()
    if existing:
        conn.close()
        raise Exception(f"Ya existe una factura #{existing['id']} generada {cycle_label} para esta venta recurrente")
    
    # Calcular fecha de vencimiento (30 días)
    issued_date = now.strftime('%Y-%m-%d')
    due_date = (now + timedelta(days=30)).strftime('%Y-%m-%d')

    # Obtener información del producto/servicio para la descripción
    service_name = sale['description'] or "Venta recurrente"
    
    if sale.get('service_id'):
        try:
            import products_services
            service = products_services.get_product_service(sale['service_id'])
            if service:
                service_name = service.get('name', service_name)
        except Exception as e:
            _log(f"Error obteniendo producto/servicio {sale['service_id']}: {e}")

    # Crear la factura con el nombre del servicio y enlace a la recurrente
    cur.execute("""
        INSERT INTO invoices (unit_id, amount, issued_date, due_date, description, paid, recurring_sale_id)
        VALUES (?, ?, ?, ?, ?, 0, ?)
    """, (unit_id, sale['amount'], issued_date, due_date, service_name, sale_id))

    conn.commit()
    invoice_id = cur.lastrowid
    
    # Actualizar last_generated en la venta recurrente
    cur.execute("UPDATE recurring_sales SET last_generated = ? WHERE id = ?", (issued_date, sale_id))
    conn.commit()
    conn.close()

    _notify_recurring_invoice(
        invoice_id=invoice_id,
        sale=sale,
        apartment=apartment,
        service_name=service_name,
        issued_date=issued_date,
        due_date=due_date,
    )

    return invoice_id
