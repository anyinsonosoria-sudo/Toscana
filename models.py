"""
Models Module
=============
Funciones de acceso a datos para el sistema de facturación.
"""
import logging
import os
from db import get_conn, get_db
from typing import List, Dict, Optional

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
from datetime import datetime

LOG_PATH = Path(__file__).parent / "run.log"
def _log(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()}Z - {msg}\n")
    except Exception:
        pass

def add_unit(number: str, owner: str, email: str = "", phone: str = "") -> int:
    """Agrega una unidad (legacy, usar apartments.add_apartment)"""
    try:
        with get_db() as conn:
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
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, number, owner, email FROM units ORDER BY number")
        rows = cur.fetchall()
        return [dict(r) for r in rows]

def add_charge(unit_id: int, description: str, amount: float, due_date: Optional[str] = None) -> int:
    """Agrega un cargo"""
    with get_db() as conn:
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
    
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO invoices(unit_id, description, amount, due_date, recurring_sale_id) VALUES(?,?,?,?,?)",
                    (unit_id, description, amount, due_date, recurring_sale_id))
        conn.commit()
        rid = cur.lastrowid
        # fetch created invoice and apartment info for notification
        cur.execute("SELECT * FROM invoices WHERE id=?", (rid,))
        inv_row = cur.fetchone()
        cur.execute("SELECT * FROM apartments WHERE id=?", (unit_id,))
        unit_row = cur.fetchone()
        # Get resident info
        cur.execute("SELECT * FROM residents WHERE unit_id=? LIMIT 1", (unit_id,))
        resident_row = cur.fetchone()
        conn.close()
    except Exception as e:
        _log(f"create_invoice DB insert/fetch failed: {e}")
        raise

    # prepare dicts
    invoice = dict(inv_row) if inv_row else {}
    unit = dict(unit_row) if unit_row else {"id": unit_id}
    resident = dict(resident_row) if resident_row else {}
    
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
                'resident_name': resident.get('name', ''),
                'resident_phone': resident.get('phone', ''),
                'resident_email': resident.get('email', '')
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
                        lf.write(f"{datetime.utcnow().isoformat()}Z - Invoice {rid} notification failed: {e}\n")
                except Exception:
                    pass
                _log(f"create_invoice notification failed for {rid}: {e}")
                # Re-lanzar el error para que el usuario lo vea
                raise RuntimeError(f"Error al enviar notificación: {str(e)}")
        else:
            try:
                log_path = Path(__file__).parent / "notifications.log"
                with open(log_path, "a", encoding="utf-8") as lf:
                    lf.write(f"{datetime.utcnow().isoformat()}Z - Invoice {rid} notification skipped: senders module not available\n")
            except Exception:
                pass
            _log(f"create_invoice notification skipped (senders missing) for {rid}")
    return rid

def list_invoices(unit_id: Optional[int] = None) -> List[Dict]:
    """Lista todas las facturas, opcionalmente filtradas por unidad"""
    with get_db() as conn:
        cur = conn.cursor()
        if unit_id:
            cur.execute("SELECT id, unit_id, description, amount, issued_date, due_date, paid FROM invoices WHERE unit_id=? ORDER BY id DESC", (unit_id,))
        else:
            cur.execute("SELECT id, unit_id, description, amount, issued_date, due_date, paid FROM invoices ORDER BY id DESC")
        rows = cur.fetchall()
        return [dict(r) for r in rows]

def get_invoice(invoice_id: int):
    """Obtiene una factura por su ID"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,))
        row = cur.fetchone()
        return dict(row) if row else None

# Alias para compatibilidad
get_invoice_by_id = get_invoice


def get_invoice_paid_amount(invoice_id: int) -> float:
    """
    Obtiene el total pagado de una factura.
    Retorna 0 si no hay pagos.
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT IFNULL(SUM(amount), 0) as total_paid
                FROM payments
                WHERE invoice_id = ?
            """, (invoice_id,))
            row = cur.fetchone()
            if row:
                row_dict = dict(row)
                return float(row_dict.get('total_paid', 0))
            return 0.0
    except Exception as e:
        logger.error(f"Error getting paid amount for invoice {invoice_id}: {e}")
        return 0.0


# ========== FUNCIONES AUXILIARES PARA PAGOS ==========

def _validate_payment(invoice_id: int, amount: float, conn) -> Dict:
    """
    Valida que el pago sea valido.
    Retorna dict con datos de la factura si es valido, lanza excepcion si no.
    """
    if amount <= 0:
        raise ValueError(f"El monto del pago debe ser mayor a cero (recibido: {amount})")
    
    cur = conn.cursor()
    
    # Verificar que la factura existe
    cur.execute("SELECT id, amount, unit_id, description FROM invoices WHERE id=?", (invoice_id,))
    invoice_row = cur.fetchone()
    if not invoice_row:
        raise ValueError(f"La factura #{invoice_id} no existe")
    
    invoice_dict = dict(invoice_row)
    
    # Verificar sobrepago
    cur.execute("SELECT IFNULL(SUM(amount),0) as paid_sum FROM payments WHERE invoice_id=?", (invoice_id,))
    current_paid = dict(cur.fetchone())["paid_sum"]
    invoice_amount = invoice_dict["amount"]
    
    if current_paid + amount > invoice_amount:
        raise ValueError(
            f"El pago de RD$ {amount:,.2f} excede el saldo pendiente de RD$ {(invoice_amount - current_paid):,.2f}"
        )
    
    invoice_dict['current_paid'] = current_paid
    return invoice_dict


def _insert_payment_record(invoice_id: int, amount: float, method: str, notes: str, conn) -> int:
    """Inserta el registro de pago en la BD. Retorna payment_id."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments(invoice_id, amount, method, notes) VALUES(?,?,?,?)",
        (invoice_id, amount, method, notes)
    )
    return cur.lastrowid


def _update_invoice_status(invoice_id: int, conn) -> float:
    """
    Actualiza el estado de la factura basado en pagos totales.
    Retorna el total pagado.
    """
    cur = conn.cursor()
    
    # Calcular total pagado
    cur.execute("""
        SELECT 
            i.amount as invoice_amount,
            IFNULL((SELECT SUM(amount) FROM payments WHERE invoice_id = i.id), 0) as total_paid
        FROM invoices i WHERE i.id = ?
    """, (invoice_id,))
    row = cur.fetchone()
    
    if not row:
        raise ValueError(f"Error al obtener datos de la factura #{invoice_id}")
    
    row_dict = dict(row)
    invoice_amount = row_dict["invoice_amount"]
    total_paid = row_dict["total_paid"]
    
    # Actualizar estado
    pending_amount = max(invoice_amount - total_paid, 0)
    is_paid = total_paid >= invoice_amount
    cur.execute(
        "UPDATE invoices SET paid=?, pending_amount=? WHERE id=?",
        (is_paid, pending_amount, invoice_id)
    )
    
    return total_paid


def _create_accounting_entry(invoice_id: int, amount: float, description: str, conn) -> None:
    """Crea entrada contable para el pago."""
    from datetime import datetime as dt_now
    cur = conn.cursor()
    payment_date = dt_now.now().strftime("%Y-%m-%d")
    
    cur.execute("""
        INSERT INTO accounting_transactions(type, description, amount, category, reference, date)
        VALUES(?, ?, ?, ?, ?, ?)
    """, ('income', f'Pago recibido: {description}', amount, 'Ventas/Facturas', f'INV-{invoice_id}', payment_date))


def _generate_account_statement_pdf(apt: Dict, invoice: Dict) -> Optional[str]:
    """
    Genera PDF del estado de cuenta.
    Retorna la ruta del archivo o None si falla.
    """
    try:
        from pathlib import Path
        import os
        
        # Obtener todas las facturas y pagos del apartamento
        unit_id = apt.get('id')
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Obtener facturas
            cur.execute("""
                SELECT id, description, amount, issued_date, due_date, paid
                FROM invoices 
                WHERE unit_id = ?
                ORDER BY issued_date DESC
                LIMIT 10
            """, (unit_id,))
            invoices = [dict(row) for row in cur.fetchall()]
            
            # Obtener pagos
            cur.execute("""
                SELECT p.id, p.amount, p.paid_date, p.method, p.invoice_id
                FROM payments p
                JOIN invoices i ON p.invoice_id = i.id
                WHERE i.unit_id = ?
                ORDER BY p.paid_date DESC
                LIMIT 10
            """, (unit_id,))
            payments = [dict(row) for row in cur.fetchall()]
        
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
    
    client_email = apt.get('resident_email') if apt else None
    client_phone = apt.get('resident_phone') if apt else None
    
    # Si no hay email en apartments, buscar en residents
    if not client_email and apt and apt.get('id'):
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT email FROM residents WHERE unit_id=? LIMIT 1", (apt['id'],))
                res_row = cur.fetchone()
                if res_row and res_row['email']:
                    client_email = res_row['email']
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
            return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None
        
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
    
    Args:
        invoice_id: ID de la factura
        amount: Monto del pago
        method: Metodo de pago (efectivo, transferencia, etc.)
        generate_receipt: Si True, genera recibo PDF
        send_notifications: Si True, envia notificaciones al cliente
        notes: Notas adicionales del pago
    
    Returns:
        ID del pago registrado
    
    Raises:
        ValueError: Si los datos son invalidos o hay sobrepago
    """
    payment_id = None
    total_paid = 0
    invoice_data = None
    
    # Fase 1: Operaciones de base de datos (transaccional)
    with get_db() as conn:
        try:
            # Validar pago
            invoice_data = _validate_payment(invoice_id, amount, conn)
            description = invoice_data.get('description', f'Pago de Factura #{invoice_id}')
            
            # Insertar pago
            payment_id = _insert_payment_record(invoice_id, amount, method, notes, conn)
            
            # Actualizar estado de factura
            total_paid = _update_invoice_status(invoice_id, conn)
            
            # Crear entrada contable
            _create_accounting_entry(invoice_id, amount, description, conn)
            
            # Commit
            conn.commit()
            _log(f"Payment {payment_id} recorded: ${amount} for invoice {invoice_id}")
            
        except Exception as e:
            conn.rollback()
            _log(f"Error recording payment for invoice {invoice_id}: {e}")
            raise
    
    # Fase 2: Operaciones externas (no transaccionales, pueden fallar sin afectar el pago)
    receipt_path = None
    
    if generate_receipt:
        receipt_path = _generate_receipt_pdf(payment_id, invoice_id, amount, method, total_paid, notes)
    
    if send_notifications:
        invoice = get_invoice(invoice_id)
        if invoice:
            # Generar estado de cuenta para adjuntar
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
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT IFNULL(SUM(amount),0) as total_invoiced FROM invoices WHERE unit_id=?", (unit_id,))
        total_invoiced_row = cur.fetchone()
        total_invoiced = dict(total_invoiced_row)["total_invoiced"] or 0
        cur.execute("""
            SELECT IFNULL(SUM(p.amount),0) as total_paid FROM payments p
            JOIN invoices i ON p.invoice_id=i.id
            WHERE i.unit_id=?
        """, (unit_id,))
        total_paid_row = cur.fetchone()
        total_paid = dict(total_paid_row)["total_paid"] or 0
        return float(total_invoiced) - float(total_paid)


# ========== VENTAS RECURRENTES ==========

def create_recurring_sales_table():
    """Crear tabla de ventas recurrentes si no existe"""
    conn = get_conn()
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
    """Crear una venta recurrente
    
    Args:
        unit_id: ID del apartamento (unit_id referencia a apartments.id)
    """
    # Validar monto positivo
    if amount <= 0:
        raise ValueError(f"El monto de la venta recurrente debe ser mayor a cero (recibido: {amount})")
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO recurring_sales (unit_id, service_id, amount, frequency, billing_day, 
                                     start_date, description, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (unit_id, service_id, amount, frequency, billing_day, start_date, description, 1 if active else 0))
    conn.commit()
    rowid = cur.lastrowid
    conn.close()
    return rowid

def list_recurring_sales() -> List[Dict]:
    """Listar todas las ventas recurrentes con info de apartamento y servicio"""
    conn = get_conn()
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
    """Activar/desactivar una venta recurrente"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE recurring_sales SET active = NOT active WHERE id = ?", (sale_id,))
    conn.commit()
    conn.close()
    return True

def duplicate_recurring_sale(sale_id: int) -> int:
    """Duplicar una venta recurrente
    
    Args:
        sale_id: ID de la venta recurrente a duplicar
        
    Returns:
        ID de la nueva venta recurrente creada
    """
    conn = get_conn()
    cur = conn.cursor()
    
    # Obtener datos de la venta recurrente original
    cur.execute("SELECT * FROM recurring_sales WHERE id = ?", (sale_id,))
    sale_row = cur.fetchone()
    
    if not sale_row:
        conn.close()
        raise Exception(f"Venta recurrente #{sale_id} no encontrada")
    
    sale = dict(sale_row)
    
    # Crear nueva venta recurrente con los mismos datos (usando solo columnas existentes)
    cur.execute("""
        INSERT INTO recurring_sales (
            unit_id, service_id, amount, frequency, billing_day, start_date, 
            end_date, description, active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sale['unit_id'], 
        sale['service_id'], 
        sale['amount'], 
        sale['frequency'], 
        sale.get('billing_day', 1),
        sale['start_date'], 
        sale['end_date'], 
        sale['description'] + " (Copia)",  # Agregar "(Copia)" al nombre
        sale['active']
    ))
    
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    
    _log(f"Venta recurrente {sale_id} duplicada como {new_id}")
    return new_id


def update_recurring_sale(sale_id: int, **fields) -> None:
    """Actualizar una venta recurrente existente"""
    if not fields:
        return
    
    ALLOWED = {'unit_id', 'service_id', 'amount', 'frequency', 'billing_day',
               'billing_time', 'start_date', 'end_date', 'description', 'active'}
    
    keys = []
    vals = []
    for k, v in fields.items():
        if k not in ALLOWED:
            continue
        keys.append(f"{k}=?")
        vals.append(v)
    
    if not keys:
        return
    
    vals.append(sale_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE recurring_sales SET {', '.join(keys)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    _log(f"Venta recurrente {sale_id} actualizada: {list(fields.keys())}")


def get_recurring_sale(sale_id: int) -> Optional[Dict]:
    """Obtener una venta recurrente por ID"""
    conn = get_conn()
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
    conn = get_conn()
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
    """Eliminar una venta recurrente y todas sus facturas asociadas
    
    Args:
        sale_id: ID de la venta recurrente
        confirmed: Si True, procede con la eliminación sin verificar
        
    Returns:
        Dict con información sobre la operación:
        - 'requires_confirmation': bool - Si requiere confirmación
        - 'invoice_count': int - Número de facturas que se eliminarán
        - 'paid_invoice_count': int - Número de facturas pagadas
        - 'total_amount': float - Monto total de facturas pagadas
        - 'deleted': bool - Si se completó la eliminación
    """
    conn = get_conn()
    cur = conn.cursor()
    
    # Obtener IDs de las facturas asociadas y su estado
    cur.execute("""
        SELECT id, paid, amount 
        FROM invoices 
        WHERE recurring_sale_id = ?
    """, (sale_id,))
    invoices = cur.fetchall()
    
    invoice_ids = [row['id'] for row in invoices]
    paid_invoices = [row for row in invoices if row['paid'] == 1]
    total_paid_amount = sum(row['amount'] for row in paid_invoices)
    
    result = {
        'requires_confirmation': False,
        'invoice_count': len(invoice_ids),
        'paid_invoice_count': len(paid_invoices),
        'total_amount': total_paid_amount,
        'deleted': False
    }
    
    # Si hay facturas pagadas y no está confirmado, retornar información
    if len(paid_invoices) > 0 and not confirmed:
        conn.close()
        result['requires_confirmation'] = True
        return result
    
    # Proceder con la eliminación
    # Eliminar pagos asociados a cada factura
    for invoice_id in invoice_ids:
        cur.execute("DELETE FROM payments WHERE invoice_id = ?", (invoice_id,))
        cur.execute("DELETE FROM accounting_transactions WHERE reference = ?", (f'INV-{invoice_id}',))
        
        # Intentar eliminar PDF si existe
        try:
            from pathlib import Path
            pdf_path = Path(__file__).parent / "static" / "invoices" / f"invoice_{invoice_id}.pdf"
            if pdf_path.exists():
                pdf_path.unlink()
                _log(f"PDF eliminado: invoice_{invoice_id}.pdf")
        except Exception as e:
            _log(f"Error eliminando PDF de factura {invoice_id}: {e}")
    
    # Eliminar todas las facturas asociadas
    cur.execute("DELETE FROM invoices WHERE recurring_sale_id = ?", (sale_id,))
    
    # Eliminar la venta recurrente
    cur.execute("DELETE FROM recurring_sales WHERE id = ?", (sale_id,))
    
    conn.commit()
    conn.close()
    _log(f"Venta recurrente {sale_id} eliminada con {len(invoice_ids)} facturas asociadas")
    
    result['deleted'] = True
    return result

def generate_invoice_from_recurring(sale_id: int) -> int:
    """Generar una factura desde una venta recurrente"""
    conn = get_conn()
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
    
    # Verificar duplicado: no generar si ya existe una factura de esta recurrente este mes
    from datetime import datetime, timedelta
    now = datetime.now()
    first_of_month = now.strftime('%Y-%m-01')
    cur.execute("""
        SELECT id FROM invoices 
        WHERE recurring_sale_id = ? AND issued_date >= ?
        LIMIT 1
    """, (sale_id, first_of_month))
    existing = cur.fetchone()
    if existing:
        conn.close()
        raise Exception(f"Ya existe una factura #{existing['id']} generada este mes para esta venta recurrente")
    
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

    # Generar PDF y enviar notificación
    try:
        from company import get_company_info
        company_info = get_company_info()
        
        # Obtener información del producto/servicio para el PDF
        service_code = 'N/A'
        additional_notes = ''
        
        if sale.get('service_id'):
            try:
                import products_services
                service = products_services.get_product_service(sale['service_id'])
                if service:
                    service_code = service.get('code', 'N/A')
                    additional_notes = service.get('additional_notes', '')
            except Exception as e:
                _log(f"Error obteniendo detalles del producto/servicio {sale['service_id']}: {e}")
        
        # Generar PDF
        import invoice_pdf
        from pathlib import Path
        pdf_dir = Path(__file__).parent / "static" / "invoices"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_filename = f"invoice_{invoice_id}.pdf"
        pdf_path = str(pdf_dir / pdf_filename)
        
        invoice_data = {
            'id': invoice_id,
            'description': service_name,  # Usar el nombre del servicio obtenido arriba
            'amount': sale['amount'],
            'issued_date': issued_date,  # Formato YYYY-MM-DD para que invoice_pdf lo formatee
            'due_date': due_date,  # Formato YYYY-MM-DD para que invoice_pdf lo formatee
            'apartment_number': apartment.get('number', ''),
            'resident_name': apartment.get('resident_name', ''),
            'resident_email': apartment.get('resident_email', ''),
            'resident_phone': apartment.get('resident_phone', ''),
            'service_code': service_code,  # Código del producto/servicio
            'notes': additional_notes  # Notas adicionales del producto
        }
        invoice_pdf.generate_invoice_pdf(invoice_data, company_info, pdf_path)
        
        # Enviar email con PDF adjunto
        notify_email = apartment.get('resident_email')
        admin_email = company_info.get('email') if company_info else None
        if not admin_email:
            admin_email = os.environ.get('SMTP_FROM') or os.environ.get('SMTP_USER')
        
        if notify_email or admin_email:
            import senders
            unit_dict = {'id': unit_id, 'number': apartment.get('number', '')}
            invoice_dict = {
                'id': invoice_id,
                'amount': sale['amount'],
                'description': service_name,
                'issued_date': issued_date,
                'due_date': due_date
            }
            
            senders.send_invoice_notification(
                invoice_dict,
                unit_dict,
                client_email=notify_email,
                admin_email=admin_email,
                attach_pdf=True,
                pdf_path=pdf_path
            )
            if notify_email:
                print(f"✓ Factura #{invoice_id} enviada a {notify_email}")
            if admin_email:
                print(f"✓ Copia enviada al admin: {admin_email}")
    except Exception as e:
        print(f"Error generando PDF o enviando email: {e}")

    return invoice_id
