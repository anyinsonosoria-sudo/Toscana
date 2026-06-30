"""
Blueprint para Facturación y Pagos (Billing)
Gestión completa de facturas, pagos, cuentas por cobrar y ventas recurrentes
"""
import logging
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, g, send_file, abort
from flask_login import login_required, current_user
from datetime import datetime
from pathlib import Path

from utils.decorators import permission_required, role_required, admin_required, audit_log
from utils.pagination import paginate
from extensions import cache, csrf
import models
import apartments
import residents
import products_services
import customization
import db
import billing

logger = logging.getLogger(__name__)

billing_bp = Blueprint('billing', __name__, url_prefix='/ventas')


def _get_request_user():
    api_user = getattr(g, 'resident_api_user', None)
    if api_user is not None:
        return api_user
    return current_user


def _get_resident_allowed_unit_ids():
    request_user = _get_request_user()
    try:
        return residents.get_allowed_unit_ids_for_user(
            request_user.id,
            fallback_email=request_user.email,
        )
    except Exception as exc:
        logger.error(f"Error resolving resident linked apartments: {exc}")
        return set()


def _get_safe_next_url(next_url=None):
    """Retorna una URL interna segura para redireccionar."""
    if next_url and next_url.startswith('/'):
        return next_url
    return url_for('billing.register_payment')


def _format_datetime_local(value):
    """Convierte fecha de BD a formato compatible con datetime-local."""
    if not value:
        return ""
    return str(value).replace(' ', 'T')[:16]


def _normalize_payment_datetime(value, fallback=None):
    """Normaliza la fecha del formulario al formato guardado en SQLite."""
    if not value:
        return fallback

    normalized = str(value).strip().replace('T', ' ')
    if len(normalized) == 10:
        return f"{normalized} 00:00:00"
    if len(normalized) == 16:
        return f"{normalized}:00"
    return normalized


def _load_payment_bundle(payment_id):
    """Obtiene pago, factura y unidad relacionados para edición o borrado."""
    from data_models.models import Payment, Invoice, Apartment
    from extensions import db as sa_db
    
    p = sa_db.session.get(Payment, payment_id)
    if not p:
        return None
        
    i = p.invoice
    a = i.apartment
    
    return {
        'payment': {
            'id': p.id,
            'invoice_id': p.invoice_id,
            'amount': p.amount,
            'paid_date': p.paid_date,
            'method': p.method,
            'notes': p.notes or '',
        },
        'invoice': {
            'id': i.id,
            'description': i.description,
            'amount': i.amount,
            'unit_id': i.unit_id,
        },
        'unit': {
            'id': a.id if a else i.unit_id,
            'number': a.number if a else 'N/A',
            'resident_name': a.resident_name if a else 'N/A',
        },
    }


def _get_payment_edit_limit(payment_id, invoice_id, invoice_amount):
    """Calcula el máximo permitido al editar un pago sin sobrepasar la factura."""
    from data_models.models import Payment
    from extensions import db as sa_db
    from sqlalchemy import func
    
    other_paid = sa_db.session.query(func.sum(Payment.amount)).filter(
        Payment.invoice_id == invoice_id, 
        Payment.id != payment_id
    ).scalar() or 0.0
    
    max_amount = max(float(invoice_amount) - float(other_paid), 0)
    return max_amount, float(other_paid)


def _sync_invoice_payment_state(invoice_id):
    """Recalcula el estado de la factura según sus pagos actuales (ORM + Dual-Write)."""
    from data_models.models import Invoice, Payment
    from extensions import db as sa_db
    from sqlalchemy import func
    
    inv = sa_db.session.get(Invoice, invoice_id)
    if not inv:
        return None, 0

    total_paid = sa_db.session.query(func.sum(Payment.amount)).filter(Payment.invoice_id == invoice_id).scalar() or 0.0
    pending_amount = max(float(inv.amount) - float(total_paid), 0)
    is_paid = 1 if float(total_paid) >= float(inv.amount) else 0

    # ORM Update
    inv.paid = bool(is_paid)
    inv.pending_amount = pending_amount
    sa_db.session.commit()

    # Dual-Write
    import db as legacy_db
    try:
        conn = legacy_db.get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE invoices SET paid = ?, pending_amount = ? WHERE id = ?",
            (is_paid, pending_amount, invoice_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Dual write failed for _sync_invoice_payment_state: {e}")

    return {
        'id': inv.id,
        'unit_id': inv.unit_id,
        'description': inv.description,
        'amount': inv.amount,
        'paid': is_paid,
        'pending_amount': pending_amount
    }, float(total_paid)


def _sync_payment_accounting_entries(invoice_id):
    """Sincroniza los asientos contables asociados a los pagos de una factura."""
    from data_models.models import Invoice, Payment, AccountingTransaction
    from extensions import db as sa_db
    import db as legacy_db
    
    inv = sa_db.session.get(Invoice, invoice_id)
    if not inv:
        return
        
    description = inv.description or f'Factura #{invoice_id}'
    ref_str = f'INV-{invoice_id}'

    # 1. ORM Delete
    AccountingTransaction.query.filter_by(reference=ref_str, type='income', category='Ventas/Facturas').delete()
    
    # 1.5. Dual-Write Delete
    try:
        conn = legacy_db.get_conn()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM accounting_transactions WHERE reference = ? AND type = ? AND category = ?",
            (ref_str, 'income', 'Ventas/Facturas')
        )
    except Exception as e:
        logger.error(f"Dual write delete failed in _sync_payment_accounting_entries: {e}")
        conn = None

    # 2. ORM Re-Insert
    payments = Payment.query.filter_by(invoice_id=invoice_id).order_by(Payment.id).all()
    for p in payments:
        payment_date = p.paid_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        txn = AccountingTransaction(
            type='income',
            description=f'Pago recibido: {description}',
            amount=p.amount,
            category='Ventas/Facturas',
            reference=ref_str,
            date=payment_date
        )
        sa_db.session.add(txn)
        sa_db.session.flush()
        
        # Dual-Write Re-Insert
        if conn:
            try:
                cur.execute(
                    """
                    INSERT INTO accounting_transactions(id, type, description, amount, category, reference, date)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (txn.id, 'income', txn.description, txn.amount, 'Ventas/Facturas', ref_str, payment_date)
                )
            except Exception as e:
                logger.error(f"Dual write insert failed in _sync_payment_accounting_entries: {e}")
    
    sa_db.session.commit()
    if conn:
        conn.commit()
        conn.close()


def _get_admin_email():
    """Obtiene el correo del administrador para alertas internas."""
    try:
        import company

        company_info = company.get_company_info() or {}
        if company_info.get('email'):
            return company_info['email']
    except Exception as exc:
        logger.warning(f"No se pudo obtener el email de empresa: {exc}")

    return os.environ.get('SMTP_FROM') or os.environ.get('SMTP_USER')


def _send_invoice_email(invoice, client_email=None, attach_pdf=False, admin_email=None):
    """Envía una factura existente por email reutilizando la notificación estándar."""
    if not invoice:
        raise ValueError("Factura no encontrada")

    if not HAS_SENDERS:
        raise RuntimeError("El modulo de envio no esta disponible")

    apt = apartments.get_apartment(invoice.get('unit_id'))
    unit_dict = {
        'id': apt.get('id') if apt else None,
        'number': apt.get('number', 'N/A') if apt else 'N/A',
        'resident_name': apt.get('resident_name', 'Cliente') if apt else 'Cliente',
    }

    invoice_payload = dict(invoice)
    if apt and not invoice_payload.get('resident_name'):
        invoice_payload['resident_name'] = apt.get('resident_name') or 'Cliente'

    pdf_path = None
    if attach_pdf:
        pdf_file = Path(__file__).parent.parent / "static" / "invoices" / f"invoice_{invoice_payload['id']}.pdf"
        if pdf_file.exists():
            pdf_path = str(pdf_file)

    import senders
    senders.send_invoice_notification(
        invoice_payload,
        unit_dict,
        client_email=client_email,
        admin_email=admin_email,
        attach_pdf=bool(pdf_path),
        pdf_path=pdf_path,
    )

    return {
        'invoice': invoice_payload,
        'unit': unit_dict,
        'client_email': client_email,
        'admin_email': admin_email,
        'attach_pdf': bool(pdf_path),
        'pdf_path': pdf_path,
    }


def _notify_admin_payment_change(action, payment, invoice, unit, previous_payment=None):
    """Envía una notificación interna al administrador cuando cambia un pago."""
    admin_email = _get_admin_email()
    if not admin_email:
        return

    try:
        import senders

        senders.send_payment_change_notification(
            action,
            payment,
            invoice,
            unit,
            admin_email=admin_email,
            previous_payment=previous_payment,
        )
    except Exception as exc:
        logger.warning(f"No se pudo enviar notificación interna del pago {payment.get('id')}: {exc}")


# ========== VISTAS PRINCIPALES ==========

@billing_bp.route('/facturas')
@login_required
@permission_required('facturacion.view')
@cache.cached(timeout=60, query_string=True)
def invoices():
    """Vista principal de facturación"""
    try:
        # Obtener apartamentos con residentes (datos consolidados)
        apts = apartments.list_apartments()
        # Crear lista de residentes desde apartamentos para compatibilidad
        res_list = []
        for apt in apts:
            if apt.get('resident_name'):  # Solo apartamentos con residentes
                res_list.append({
                    'id': apt['id'],
                    'name': apt['resident_name'],
                    'unit_number': apt['number'],
                    'email': apt.get('resident_email'),
                    'phone': apt.get('resident_phone'),
                    'role': apt.get('resident_role', 'tenant')
                })
        
        svcs = products_services.list_products_services(active_only=True)
        invoices_list = models.list_invoices()
        units_dict = {u["id"]: u for u in apartments.list_apartments()}
        
        # Obtener filtros de búsqueda
        search_resident = request.args.get("search_resident", "").strip()
        search_date_from = request.args.get("search_date_from", "").strip()
        search_date_to = request.args.get("search_date_to", "").strip()
        
        # Filtrar facturas
        if search_resident or search_date_from or search_date_to:
            filtered_invoices = []
            for inv in invoices_list:
                # Filtro por residente
                if search_resident:
                    unit_id = inv.get("unit_id")
                    resident_found = False
                    for res in res_list:
                        if res.get("id") == unit_id:  # Ahora id es del apartamento
                            if search_resident.lower() in res.get("name", "").lower():
                                resident_found = True
                                break
                    if not resident_found:
                        continue
                
                # Filtro por fecha
                if search_date_from and inv.get("issued_date", "") < search_date_from:
                    continue
                if search_date_to and inv.get("issued_date", "") > search_date_to:
                    continue
                
                filtered_invoices.append(inv)
            invoices_list = filtered_invoices
            
    except Exception as e:
        logger.error(f"Error loading invoices data: {e}")
        res_list = []
        svcs = []
        invoices_list = []
        units_dict = []
    
    # Obtener ventas recurrentes
    try:
        recurring_sales = models.list_recurring_sales()
    except Exception as e:
        logger.warning(f"Error loading recurring sales: {e}")
        recurring_sales = []
    
    # Get customization settings
    try:
        custom_settings = customization.get_settings_with_defaults()
    except Exception as e:
        logger.warning(f"Error loading customization: {e}")
        custom_settings = {}
    
    # Calcular montos pagados por factura
    invoice_paid_amounts = {}
    for inv in invoices_list:
        invoice_paid_amounts[inv['id']] = models.get_invoice_paid_amount(inv['id'])

    return render_template("facturacion.html", 
                         residents=res_list, 
                         services=svcs,
                         invoices=invoices_list,
                         units=units_dict,
                         recurring_sales=recurring_sales,
                         invoice_paid_amounts=invoice_paid_amounts,
                         now=datetime.now(),
                         search_resident=request.args.get("search_resident", ""),
                         search_date_from=request.args.get("search_date_from", ""),
                         search_date_to=request.args.get("search_date_to", ""),
                         customization=custom_settings)


@billing_bp.route('/pagos')
@login_required
@permission_required('facturacion.view')
@cache.cached(timeout=60, query_string=True)
def payments():
    """Vista de Pagos Recibidos"""
    try:
        res_list = residents.list_residents()
        invoices = models.list_invoices()
        
        # Obtener todos los pagos individuales
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT p.*, i.description as invoice_desc, i.unit_id, i.amount as invoice_amount,
                   a.number as apt_number, a.resident_name as apt_resident
            FROM payments p
            JOIN invoices i ON p.invoice_id = i.id
            LEFT JOIN apartments a ON i.unit_id = a.id
            ORDER BY p.paid_date DESC
        """)
        payments_list = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        # Calcular montos pagados por factura para los templates
        invoice_paid_amounts = {}
        for inv in invoices:
            invoice_paid_amounts[inv['id']] = models.get_invoice_paid_amount(inv['id'])
        
        custom_settings = customization.get_settings_with_defaults()
    except Exception as e:
        logger.error(f"Error loading payments: {e}")
        res_list = []
        invoices = []
        payments_list = []
        invoice_paid_amounts = {}
        custom_settings = {}
    
    return render_template("pagos.html", 
                         residents=res_list,
                         invoices=invoices,
                         invoice_paid_amounts=invoice_paid_amounts,
                         payments=payments_list,
                         now=datetime.now(),
                         customization=custom_settings)


@billing_bp.route('/cuentas-cobrar')
@login_required
@permission_required('facturacion.view')
@cache.cached(timeout=60, query_string=True)
def accounts_receivable():
    """Vista de Cuentas por Cobrar"""
    try:
        import apartments as apartments_module
        res_list = residents.list_residents()
        invoices = models.list_invoices()
        apartments_list = apartments_module.list_apartments()
        
        # Calcular montos pagados por factura para los templates
        invoice_paid_amounts = {}
        for inv in invoices:
            invoice_paid_amounts[inv['id']] = models.get_invoice_paid_amount(inv['id'])
        
        custom_settings = customization.get_settings_with_defaults()
    except Exception as e:
        logger.error(f"Error loading accounts receivable: {e}")
        res_list = []
        invoices = []
        apartments_list = []
        invoice_paid_amounts = {}
        custom_settings = {}
    
    return render_template("cuentas_cobrar.html", 
                         residents=res_list,
                         invoices=invoices,
                         invoice_paid_amounts=invoice_paid_amounts,
                         apartments=apartments_list,
                         now=datetime.now(),
                         customization=custom_settings)


@billing_bp.route('/recurrentes')
@login_required
@permission_required('facturacion.view')
def recurring_sales():
    """Vista de Ventas Recurrentes"""
    try:
        # Obtener apartamentos con residentes (datos consolidados)
        apts = apartments.list_apartments()
        # Crear lista de residentes desde apartamentos para compatibilidad
        res_list = []
        for apt in apts:
            if apt.get('resident_name'):  # Solo apartamentos con residentes
                res_list.append({
                    'id': apt['id'],
                    'name': apt['resident_name'],
                    'unit_id': apt['id'],  # Agregar unit_id para el lookup
                    'unit_number': apt['number'],
                    'email': apt.get('resident_email'),
                    'phone': apt.get('resident_phone'),
                    'role': apt.get('resident_role', 'tenant')
                })
        
        svcs = products_services.list_products_services(active_only=True)
        recurring_sales_list = models.list_recurring_sales()
        custom_settings = customization.get_settings_with_defaults()
    except Exception as e:
        logger.error(f"Error in recurring_sales: {e}")
        apts = []
        res_list = []
        svcs = []
        recurring_sales_list = []
        custom_settings = {}
    
    return render_template("ventas_recurrentes.html", 
                         residents=res_list,
                         apartments=apts,
                         services=svcs,
                         recurring_sales=recurring_sales_list,
                         now=datetime.now(),
                         customization=custom_settings)


@billing_bp.route('/registrar-pago')
@login_required
@permission_required('facturacion.create')
@cache.cached(timeout=60, query_string=True)
def register_payment():
    """Vista para registrar pagos de facturas pendientes"""
    try:
        res_list = residents.list_residents()
        invoices = models.list_invoices()
        custom_settings = customization.get_settings_with_defaults()
        
        # Obtener todos los pagos individuales con información del cliente y apartamento
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                   p.id,
                   p.invoice_id,
                   p.amount,
                   p.paid_date,
                   p.method,
                   i.description as invoice_desc, 
                   i.unit_id, 
                   i.amount as invoice_amount,
                   a.resident_name as client_name,
                   a.number as apartment_number
            FROM payments p
            JOIN invoices i ON p.invoice_id = i.id
            LEFT JOIN apartments a ON i.unit_id = a.id
            ORDER BY p.paid_date DESC
        """)
        payments_list = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        # Facturas pendientes con info de cliente y balance
        pending_invoices = []
        try:
            conn2 = db.get_conn()
            cur2 = conn2.cursor()
            cur2.execute("""
                SELECT i.*, a.resident_name as client_name, a.number as apartment_number,
                       COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as total_paid
                FROM invoices i
                LEFT JOIN apartments a ON i.unit_id = a.id
                WHERE i.paid = 0
                ORDER BY i.id DESC
            """)
            for row in cur2.fetchall():
                inv = dict(row)
                inv['remaining'] = max(inv['amount'] - inv['total_paid'], 0)
                pending_invoices.append(inv)
            conn2.close()
        except Exception as e2:
            logger.error(f"Error loading pending invoices: {e2}")
            for inv in invoices:
                if not inv.get('paid'):
                    pending_invoices.append(inv)
    except Exception as e:
        logger.error(f"Error loading payment data: {e}")
        res_list = []
        pending_invoices = []
        invoices = []
        payments_list = []
        custom_settings = {}
    
    return render_template("registrar_pago.html", 
                         residents=res_list,
                         invoices=pending_invoices,
                         all_invoices=invoices,
                         payments=payments_list,
                         now=datetime.now(),
                         customization=custom_settings)


# ========== OPERACIONES DE FACTURAS ==========

@billing_bp.route('/facturas/create', methods=['POST'], endpoint='create_factura')
@login_required
@permission_required('facturacion.create')
@audit_log('facturacion.crear', 'Crear factura')
def create_invoice():
    """Crear nueva factura con múltiples líneas"""
    try:
        resident_id = int(request.form.get("resident_id", 0))
    except Exception:
        flash("Residente válido requerido.", "error")
        return redirect(url_for("billing.invoices", tab="invoices"))
    
    # Obtener múltiples servicios del formulario
    service_codes = request.form.getlist("service_code[]")
    quantities = request.form.getlist("quantity[]")
    amounts = request.form.getlist("amount[]")
    descriptions = request.form.getlist("line_description[]")
    
    if not service_codes or len(service_codes) == 0:
        flash("Debe agregar al menos un servicio.", "error")
        return redirect(url_for("billing.invoices", tab="invoices"))
    
    notify_email = request.form.get("notify_email", "").strip()
    notify_phone = request.form.get("notify_phone", "").strip()
    send_whatsapp = request.form.get("send_whatsapp") == "on"
    attach_pdf = request.form.get("attach_pdf") == "on"
    
    # Nota: Email y teléfono son opcionales
    # Si se proporcionan, se enviarán notificaciones automáticamente
    # Si no se proporcionan, se crea la factura sin notificaciones
    
    phone_to_send = notify_phone if send_whatsapp else None
    
    print(f"\n{'='*60}")
    print(f"[BLUEPRINT] Creando factura:")
    print(f"  - Resident ID: {resident_id}")
    print(f"  - Email cliente: {notify_email or 'NO PROPORCIONADO'}")
    print(f"  - Teléfono: {phone_to_send or 'NO PROPORCIONADO'}")
    print(f"  - Adjuntar PDF: {attach_pdf}")
    print(f"{'='*60}\n")
    
    try:
        inv_id = billing.create_invoice_with_lines(
            resident_id,
            service_codes,
            quantities,
            amounts,
            descriptions,
            notify_email=notify_email if notify_email else None,
            notify_phone=phone_to_send,
            attach_pdf=attach_pdf
        )
        
        print(f"\n✅ Factura #{inv_id} creada exitosamente\n")
        
        # Mensaje de éxito con información sobre notificaciones
        if notify_email:
            flash(f"✅ Factura #{inv_id} creada y enviada a {notify_email}", "success")
        else:
            flash(f"✅ Factura #{inv_id} creada (sin notificación automática)", "info")
            
        cache.clear()
    except Exception as e:
        print(f"\n❌ ERROR creando factura: {e}\n")
        import traceback
        traceback.print_exc()
        flash(f"Error al crear factura: {e}", "error")
    
    return redirect(url_for("billing.invoices", tab="invoices"))


@billing_bp.route('/facturas/edit/<int:invoice_id>', methods=['GET', 'POST'], endpoint='edit_factura')
@login_required
@permission_required('facturacion.edit')
@audit_log('facturacion.editar', 'Editar factura')
def edit_invoice(invoice_id):
    """Editar factura existente"""
    if request.method == "POST":
        try:
            description = request.form.get("description", "").strip()
            amount = float(request.form.get("amount", 0))
            due_date = request.form.get("due_date", "").strip()
            notes = request.form.get("notes", "").strip()
            
            conn = db.get_conn()
            cur = conn.cursor()
            cur.execute("""
                UPDATE invoices 
                SET description = ?, amount = ?, due_date = ?, notes = ?
                WHERE id = ?
            """, (description, amount, due_date, notes, invoice_id))
            conn.commit()
            conn.close()
            
            flash(f"Factura #{invoice_id} actualizada exitosamente.", "success")
            cache.clear()
        except Exception as e:
            flash(f"Error al actualizar factura: {e}", "error")
        return redirect(url_for("billing.invoices", tab="invoices"))
    
    # GET: mostrar formulario de edición
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        invoice = dict(cur.fetchone())
        conn.close()
        custom_settings = customization.get_settings_with_defaults()
        return render_template("edit_factura.html", invoice=invoice, customization=custom_settings)
    except Exception as e:
        flash(f"Error al cargar factura: {e}", "error")
        return redirect(url_for("billing.invoices", tab="invoices"))


@billing_bp.route('/facturas/delete/<int:invoice_id>', methods=['POST'])
@login_required
@permission_required('facturacion.delete')
@audit_log('facturacion.eliminar', 'Eliminar factura')
def delete_invoice(invoice_id):
    """Eliminar una factura"""
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        
        # Verificar si la factura existe y obtener información
        cur.execute("SELECT id, unit_id, amount, paid FROM invoices WHERE id = ?", (invoice_id,))
        invoice = cur.fetchone()
        
        if not invoice:
            flash("Factura no encontrada", "error")
            return redirect(url_for("billing.invoices", tab="invoices"))
        
        # Eliminar pagos asociados primero
        cur.execute("DELETE FROM payments WHERE invoice_id = ?", (invoice_id,))
        
        # Eliminar transacciones contables asociadas
        cur.execute("DELETE FROM accounting_transactions WHERE reference = ?", (f'INV-{invoice_id}',))
        
        # Eliminar la factura
        cur.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        
        conn.commit()
        conn.close()
        
        # Intentar eliminar el PDF si existe
        try:
            pdf_path = Path(__file__).parent.parent / "static" / "invoices" / f"invoice_{invoice_id}.pdf"
            if pdf_path.exists():
                pdf_path.unlink()
        except Exception as e:
            logger.warning(f"Error eliminando PDF: {e}")
        
        flash(f"Factura #{invoice_id} eliminada exitosamente", "success")
        cache.clear()
    except Exception as e:
        flash(f"Error al eliminar factura: {e}", "error")
    
    return redirect(url_for("billing.invoices", tab="invoices"))


@billing_bp.route('/facturas/duplicate/<int:invoice_id>', methods=['POST'])
@login_required
@permission_required('facturacion.create')
@audit_log('facturacion.duplicar', 'Duplicar factura')
def duplicate_invoice(invoice_id):
    """Obtener datos de factura para duplicar (el usuario revisará antes de guardar)"""
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        
        # Obtener factura original
        cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        original = dict(cur.fetchone())
        conn.close()
        
        if not original:
            return jsonify({"success": False, "error": "Factura no encontrada"}), 404
        
        # Devolver los datos para pre-llenar el formulario
        return jsonify({
            "success": True,
            "invoice": {
                "unit_id": original['unit_id'],
                "description": original['description'],
                "amount": original['amount'],
                "notes": f"[DUPLICADO DE #{invoice_id}] {original.get('notes', '')}"
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@billing_bp.route('/facturas/partial-payment/<int:invoice_id>', methods=['POST'])
@login_required
@permission_required('facturacion.create')
@audit_log('facturacion.pago_parcial', 'Registrar pago parcial')
def partial_payment(invoice_id):
    """Registrar pago parcial de factura"""
    try:
        # Obtener datos del formulario
        received_amount = request.form.get("received_amount", None)
        method = request.form.get("method", "transferencia")
        
        if received_amount is None or str(received_amount).strip() == "":
            flash("Debes ingresar una cantidad recibida.", "error")
            return redirect(url_for("billing.invoices", tab="pending"))
        
        received_amount = str(received_amount).replace(",", ".").strip()
        try:
            received = float(received_amount)
        except Exception:
            flash(f"Cantidad recibida inválida: '{received_amount}'", "error")
            return redirect(url_for("billing.invoices", tab="pending"))
        
        # Validar monto
        if received <= 0:
            flash("La cantidad recibida debe ser mayor a cero.", "error")
            return redirect(url_for("billing.invoices", tab="pending"))
        
        # Obtener factura y saldo pendiente
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        invoice_row = cur.fetchone()
        if not invoice_row:
            flash("Factura no encontrada.", "error")
            conn.close()
            return redirect(url_for("billing.invoices", tab="pending"))
        invoice = dict(invoice_row)
        
        cur.execute("SELECT COALESCE(SUM(amount), 0) as paid FROM payments WHERE invoice_id = ?", (invoice_id,))
        total_paid_row = cur.fetchone()
        total_paid = dict(total_paid_row)['paid']
        remaining = invoice['amount'] - total_paid
        
        # If invoice is already fully paid, reject
        if remaining <= 0:
            flash("Esta factura ya está completamente pagada.", "error")
            conn.close()
            return redirect(url_for("billing.invoices", tab="pending"))
        
        # Calcular el monto a registrar y cambio
        if method == "efectivo":
            # En efectivo: permitir cantidad mayor y calcular cambio
            change = 0
            if received > remaining:
                change = received - remaining
                amount_to_register = remaining  # Registrar solo lo que falta
                flash(f"Pago completo registrado. Cambio a devolver: RD${change:,.2f}", "success")
            else:
                amount_to_register = received  # Registrar lo que se recibió
        else:
            # Otros métodos: no permitir cantidad mayor al pendiente
            if received > remaining:
                flash(f"La cantidad recibida excede el saldo pendiente (RD${remaining:,.2f}).", "error")
                conn.close()
                return redirect(url_for("billing.invoices", tab="pending"))
            amount_to_register = received
        
        conn.close()
        
        # Obtener notas del formulario
        notes = request.form.get("notes", "").strip()
        
        # Registrar pago - SIEMPRE generar recibo y enviar notificaciones
        payment_id = models.record_payment(
            invoice_id, 
            amount_to_register, 
            method, 
            generate_receipt=True, 
            send_notifications=True,
            notes=notes
        )
        
        # Si el pago completa la factura, marcarla como pagada
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(amount), 0) as new_paid FROM payments WHERE invoice_id = ?", (invoice_id,))
        new_total_paid_row = cur.fetchone()
        new_total_paid = dict(new_total_paid_row)['new_paid']
        if new_total_paid >= invoice['amount']:
            cur.execute("UPDATE invoices SET paid = 1 WHERE id = ?", (invoice_id,))
            conn.commit()
        conn.close()
        
        # Mensaje de pago registrado
        if method == "efectivo" and received > remaining:
            pass  # Ya mostramos el mensaje con cambio arriba
        elif amount_to_register < remaining:
            new_remaining = remaining - amount_to_register
            flash(f"Pago parcial de RD${amount_to_register:.2f} registrado. Saldo pendiente: RD${new_remaining:.2f}", "success")
        else:
            flash(f"Pago completo de RD${amount_to_register:.2f} registrado exitosamente.", "success")
        
        cache.clear()
    except Exception as e:
        flash(f"Error al registrar pago: {e}", "error")
    
    return redirect(url_for("billing.register_payment"))


# ========== OPERACIONES DE PAGOS ==========

@billing_bp.route('/pagos/edit/<int:payment_id>')
@login_required
@permission_required('facturacion.edit')
def edit_payment(payment_id):
    """Formulario para editar un pago registrado."""
    conn = None
    try:
        conn = db.get_conn()
        payment_bundle = _load_payment_bundle(payment_id, conn)
        if not payment_bundle:
            flash(f"Pago #{payment_id} no encontrado", "error")
            return redirect(_get_safe_next_url(request.args.get('next')))

        max_amount, other_paid = _get_payment_edit_limit(
            payment_id,
            payment_bundle['invoice']['id'],
            payment_bundle['invoice']['amount'],
            conn,
        )
        payment_bundle['payment']['paid_date_form'] = _format_datetime_local(payment_bundle['payment'].get('paid_date'))

        try:
            custom_settings = customization.get_settings_with_defaults()
        except Exception:
            custom_settings = {}

        return render_template(
            'edit_payment.html',
            payment=payment_bundle['payment'],
            invoice=payment_bundle['invoice'],
            unit=payment_bundle['unit'],
            max_amount=max_amount,
            other_paid=other_paid,
            next_url=_get_safe_next_url(request.args.get('next')),
            customization=custom_settings,
        )
    except Exception as exc:
        logger.error(f"Error cargando pago #{payment_id} para edición: {exc}")
        flash(f"Error cargando pago: {exc}", "error")
        return redirect(_get_safe_next_url(request.args.get('next')))
    finally:
        if conn:
            conn.close()


@billing_bp.route('/pagos/edit/<int:payment_id>', methods=['POST'], endpoint='update_payment')
@login_required
@permission_required('facturacion.edit')
@audit_log('facturacion.editar_pago', 'Editar pago')
def update_payment(payment_id):
    """Actualiza un pago existente y notifica solo al administrador."""
    next_url = _get_safe_next_url(request.form.get('next'))
    edit_url = url_for('billing.edit_payment', payment_id=payment_id, next=next_url)

    amount_raw = (request.form.get('amount') or '').replace(',', '.').strip()
    method = (request.form.get('method') or '').strip() or 'transferencia'
    notes = (request.form.get('notes') or '').strip()
    paid_date = request.form.get('paid_date')

    try:
        amount = float(amount_raw)
    except ValueError:
        flash('Debes indicar un monto válido.', 'error')
        return redirect(edit_url)

    if amount <= 0:
        flash('El monto del pago debe ser mayor a cero.', 'error')
        return redirect(edit_url)

    try:
        payment_bundle = _load_payment_bundle(payment_id)
        if not payment_bundle:
            flash(f'Pago #{payment_id} no encontrado', 'error')
            return redirect(next_url)

        max_amount, _ = _get_payment_edit_limit(
            payment_id,
            payment_bundle['invoice']['id'],
            payment_bundle['invoice']['amount']
        )
        if amount > max_amount:
            flash(
                f'El monto excede el saldo disponible para la factura (RD${max_amount:,.2f}).',
                'error',
            )
            return redirect(edit_url)

        previous_payment = dict(payment_bundle['payment'])
        normalized_paid_date = _normalize_payment_datetime(paid_date, previous_payment.get('paid_date'))

        # ORM Update
        from data_models.models import Payment
        from extensions import db as sa_db
        p = sa_db.session.get(Payment, payment_id)
        p.amount = amount
        p.method = method
        p.notes = notes
        p.paid_date = normalized_paid_date
        sa_db.session.commit()
        
        # Dual-Write
        import db as legacy_db
        try:
            conn = legacy_db.get_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE payments SET amount = ?, method = ?, notes = ?, paid_date = ? WHERE id = ?",
                (amount, method, notes, normalized_paid_date, payment_id),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Dual write failed for edit_payment: {e}")

        _sync_invoice_payment_state(payment_bundle['invoice']['id'])
        _sync_payment_accounting_entries(payment_bundle['invoice']['id'])

        updated_bundle = _load_payment_bundle(payment_id)
        cache.clear()
    except Exception as exc:
        sa_db.session.rollback()
        logger.error(f"Error editando pago #{payment_id}: {exc}")
        flash(f'Error al editar pago: {exc}', 'error')
        return redirect(edit_url)

    if updated_bundle:
        _notify_admin_payment_change(
            'edited',
            updated_bundle['payment'],
            updated_bundle['invoice'],
            updated_bundle['unit'],
            previous_payment=previous_payment,
        )

    flash(f'Pago #{payment_id} actualizado correctamente', 'success')
    return redirect(next_url)

@billing_bp.route('/pagos/delete/<int:payment_id>', methods=['POST'])
@login_required
@permission_required('facturacion.delete')
@audit_log('facturacion.eliminar_pago', 'Eliminar pago')
def delete_payment(payment_id):
    """Eliminar un pago registrado"""
    next_url = _get_safe_next_url(request.form.get('next'))
    try:
        payment_bundle = _load_payment_bundle(payment_id)

        if payment_bundle:
            # ORM Delete
            from data_models.models import Payment
            from extensions import db as sa_db
            p = sa_db.session.get(Payment, payment_id)
            if p:
                sa_db.session.delete(p)
                sa_db.session.commit()
                
            # Dual-Write
            import db as legacy_db
            try:
                conn = legacy_db.get_conn()
                cur = conn.cursor()
                cur.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Dual write failed for delete_payment: {e}")

            _sync_invoice_payment_state(payment_bundle['invoice']['id'])
            _sync_payment_accounting_entries(payment_bundle['invoice']['id'])

            _notify_admin_payment_change(
                'deleted',
                payment_bundle['payment'],
                payment_bundle['invoice'],
                payment_bundle['unit'],
            )

            flash(f"Pago #{payment_id} eliminado correctamente", "success")
            cache.clear()
        else:
            flash(f"Pago #{payment_id} no encontrado", "error")

    except Exception as e:
        sa_db.session.rollback()
        flash(f"Error al eliminar pago: {str(e)}", "error")

    return redirect(next_url)


# ========== VENTAS RECURRENTES ==========

@billing_bp.route('/facturas/recurring/create', methods=['POST'])
@login_required
@permission_required('facturacion.create')
@audit_log('facturacion.crear_recurrente', 'Crear venta recurrente')
def create_recurring():
    """Crear una venta recurrente y generar primera factura automáticamente"""
    try:
        resident_id = int(request.form.get("resident_id", 0))
        service_id = int(request.form.get("service_id", 0))
        amount = float(request.form.get("amount", 0))
        frequency = request.form.get("frequency", "monthly")
        billing_day = int(request.form.get("billing_day", 1))
        billing_time = request.form.get("billing_time", "08:00").strip()
        start_date = request.form.get("start_date", "")
        end_date = request.form.get("end_date", "")
        description = request.form.get("description", "")
        active = request.form.get("active", "1") == "1"
        attach_pdf = request.form.get("attach_pdf", "0") == "1"
        
        if resident_id <= 0 or amount <= 0:
            flash("Datos inválidos", "error")
            return redirect(url_for("billing.invoices", tab="recurring"))
        
        # Obtener unit_id del resident_id (que en realidad es el apartamento)
        # Crear venta recurrente usando models.add_recurring_sale
        sale_id = models.add_recurring_sale(
            unit_id=resident_id,
            service_id=service_id,
            amount=amount,
            frequency=frequency,
            billing_day=billing_day,
            start_date=start_date,
            description=description,
            active=active
        )
        
        # Update extra fields if needed
        if end_date or billing_time != "08:00":
            models.update_recurring_sale(sale_id, end_date=end_date if end_date else None, billing_time=billing_time)
        
        # Generar la primera factura automáticamente
        try:
            invoice_id = models.generate_invoice_from_recurring(sale_id)
            flash(f"Venta recurrente #{sale_id} creada y primera factura #{invoice_id} generada exitosamente", "success")
        except Exception as gen_error:
            flash(f"Venta recurrente #{sale_id} creada, pero hubo un error al generar la primera factura: {gen_error}", "warning")
        
        cache.clear()
    except Exception as e:
        flash(f"Error al crear venta recurrente: {e}", "error")
    
    return redirect(url_for("billing.invoices", tab="recurring"))


@billing_bp.route('/facturas/recurring/toggle/<int:sale_id>', methods=['POST'])
@login_required
@permission_required('facturacion.edit')
def toggle_recurring(sale_id):
    """Activar/desactivar venta recurrente"""
    try:
        models.toggle_recurring_sale(sale_id)
        cache.clear()
    except Exception as e:
        logger.error(f"Error toggling recurring sale: {e}")
    return redirect(url_for('billing.invoices', tab='recurring'))


@billing_bp.route('/facturas/recurring/edit/<int:sale_id>', methods=['POST'])
@login_required
@permission_required('facturacion.edit')
@audit_log('facturacion.editar_recurrente', 'Editar venta recurrente')
def edit_recurring(sale_id):
    """Editar una venta recurrente existente"""
    try:
        fields = {}
        
        unit_id = request.form.get("unit_id")
        if unit_id:
            fields["unit_id"] = int(unit_id)
        
        service_id = request.form.get("service_id")
        if service_id:
            fields["service_id"] = int(service_id)
        
        amount = request.form.get("amount")
        if amount:
            fields["amount"] = float(amount)
        
        frequency = request.form.get("frequency")
        if frequency:
            fields["frequency"] = frequency
        
        billing_day = request.form.get("billing_day")
        if billing_day:
            fields["billing_day"] = int(billing_day)
        
        billing_time = request.form.get("billing_time")
        if billing_time:
            fields["billing_time"] = billing_time
        
        description = request.form.get("description")
        if description is not None:
            fields["description"] = description.strip()
        
        start_date = request.form.get("start_date")
        if start_date:
            fields["start_date"] = start_date
        
        end_date = request.form.get("end_date")
        if end_date is not None:
            fields["end_date"] = end_date if end_date else None
        
        active = request.form.get("active")
        if active is not None:
            fields["active"] = 1 if active == "1" else 0
        
        models.update_recurring_sale(sale_id, **fields)
        cache.clear()
        flash(f"Venta recurrente #{sale_id} actualizada exitosamente", "success")
    except Exception as e:
        logger.error(f"Error editing recurring sale: {e}")
        flash(f"Error al editar venta recurrente: {e}", "error")
    
    return redirect(url_for('billing.recurring_sales'))


@billing_bp.route('/facturas/recurring/generate/<int:sale_id>', methods=['POST'])
@login_required
@permission_required('facturacion.create')
@audit_log('facturacion.generar_recurrente', 'Generar factura recurrente')
def generate_recurring(sale_id):
    """Generar factura desde venta recurrente"""
    try:
        invoice_id = models.generate_invoice_from_recurring(sale_id)
        cache.clear()
        return jsonify({"success": True, "invoice_id": invoice_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@billing_bp.route('/facturas/recurring/last-invoice/<int:sale_id>', methods=['GET'])
@login_required
@permission_required('facturacion.view')
def get_last_invoice_from_recurring(sale_id):
    """Obtener la última factura generada de una venta recurrente"""
    try:
        invoice_id = models.get_last_invoice_from_recurring(sale_id)
        if invoice_id:
            return jsonify({"success": True, "invoice_id": invoice_id})
        else:
            return jsonify({"success": False, "error": "No hay facturas generadas para esta venta recurrente"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@billing_bp.route('/facturas/recurring/duplicate/<int:sale_id>', methods=['POST'])
@login_required
@permission_required('facturacion.create')
@audit_log('facturacion.duplicar_recurrente', 'Duplicar venta recurrente')
def duplicate_recurring(sale_id):
    """Duplicar venta recurrente"""
    try:
        models.duplicate_recurring_sale(sale_id)
        cache.clear()
    except Exception as e:
        logger.error(f"Error duplicating recurring sale: {e}")
    return redirect(url_for('billing.invoices', tab='recurring'))


@billing_bp.route('/facturas/recurring/delete/<int:sale_id>', methods=['POST'])
@login_required
@permission_required('facturacion.delete')
@audit_log('facturacion.eliminar_recurrente', 'Eliminar venta recurrente')
def delete_recurring(sale_id):
    """Eliminar venta recurrente"""
    try:
        result = models.delete_recurring_sale(sale_id, confirmed=True)
        if result.get('deleted'):
            flash(f"Venta recurrente #{sale_id} eliminada con {result.get('invoice_count', 0)} facturas asociadas", "success")
        else:
            flash(f"No se pudo eliminar la venta recurrente #{sale_id}", "error")
        cache.clear()
    except Exception as e:
        logger.error(f"Error deleting recurring sale: {e}")
        flash(f"Error al eliminar venta recurrente: {e}", "error")
    return redirect(url_for('billing.invoices', tab='recurring'))


@billing_bp.route('/facturas/recurring/process-due', methods=['POST'])
@login_required
@permission_required('facturacion.create')
@audit_log('facturacion.procesar_recurrentes', 'Procesar facturas recurrentes pendientes')
def process_due_recurring():
    """Procesar manualmente todas las facturas recurrentes que deben generarse hoy."""
    try:
        result = models.process_due_recurring_invoices()
        generated = len(result.get('generated', []))
        skipped = len(result.get('skipped', []))
        errors = result.get('errors', [])
        msg = f"Procesamiento completado: {generated} factura(s) generada(s), {skipped} omitida(s)"
        if errors:
            msg += f", {len(errors)} error(es): {'; '.join(errors[:3])}"
            flash(msg, "warning")
        else:
            flash(msg, "success")
        cache.clear()
    except Exception as e:
        logger.error(f"Error processing due recurring invoices: {e}")
        flash(f"Error al procesar facturas recurrentes: {e}", "error")
    return redirect(url_for('billing.recurring_sales'))


@billing_bp.route('/facturas/recurring/resend-latest', methods=['POST'])
@login_required
@permission_required('facturacion.view')
@audit_log('facturacion.reenviar_recurrentes', 'Reenviar correos de facturas recurrentes')
def resend_latest_recurring_invoices():
    """Reenvía la última factura generada para cada venta recurrente activa."""
    try:
        admin_email = _get_admin_email()
        recurring_sales = [sale for sale in models.list_recurring_sales() if sale.get('active')]
        sent = []
        skipped = []
        errors = []

        for sale in recurring_sales:
            sale_id = sale['id']
            client_email = (sale.get('resident_email') or '').strip()

            if not client_email:
                skipped.append(f"venta #{sale_id} sin email")
                continue

            invoice_id = models.get_last_invoice_from_recurring(sale_id)
            if not invoice_id:
                skipped.append(f"venta #{sale_id} sin factura generada")
                continue

            invoice = models.get_invoice_by_id(invoice_id)
            if not invoice:
                errors.append(f"venta #{sale_id}: factura #{invoice_id} no encontrada")
                continue

            try:
                _send_invoice_email(
                    invoice,
                    client_email=client_email,
                    attach_pdf=True,
                    admin_email=admin_email,
                )
                sent.append(f"factura #{invoice_id} a {client_email}")
            except Exception as exc:
                logger.error(f"Error reenviando factura recurrente #{invoice_id}: {exc}")
                errors.append(f"factura #{invoice_id}: {exc}")

        msg = f"Reenvío completado: {len(sent)} correo(s) enviado(s), {len(skipped)} omitido(s)"
        if errors:
            msg += f", {len(errors)} error(es): {'; '.join(errors[:3])}"
            flash(msg, "warning")
        else:
            flash(msg, "success")
    except Exception as e:
        logger.error(f"Error reenviando facturas recurrentes: {e}")
        flash(f"Error al reenviar facturas recurrentes: {e}", "error")

    return redirect(url_for('billing.recurring_sales'))


@billing_bp.route('/facturas/api/invoice/<int:invoice_id>', methods=['GET'])
@login_required
@permission_required('facturacion.view')
def get_invoice_api(invoice_id):
    """Obtener datos de una factura por API"""
    try:
        invoice = models.get_invoice(invoice_id)
        if not invoice:
            return jsonify({"success": False, "error": "Factura no encontrada"}), 404
        
        paid_amount = models.get_invoice_paid_amount(invoice_id)
        return jsonify({
            "success": True,
            "invoice": invoice,
            "paid_amount": paid_amount
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ========== VISUALIZACION DE PDF ==========

@billing_bp.route('/facturas/pdf/<int:invoice_id>', endpoint='view_invoice_pdf')
@login_required
def view_invoice_pdf(invoice_id):
    """Ver/descargar PDF de una factura"""
    try:
        request_user = _get_request_user()
        # Verificar que la factura existe
        invoice = models.get_invoice_by_id(invoice_id)
        if not invoice:
            flash("Factura no encontrada", "error")
            if request_user.role == 'resident':
                return redirect(url_for('dashboard'))
            return redirect(url_for('billing.invoices'))
        
        # Validación de propiedad para residentes o permisos para operadores/admins
        if request_user.role == 'resident':
            allowed_unit_ids = _get_resident_allowed_unit_ids()
            if invoice.get('unit_id') not in allowed_unit_ids:
                flash("Acceso denegado: esta factura no pertenece a su apartamento", "error")
                return redirect(url_for('dashboard'))
        else:
            from utils.permissions import check_permission
            if not check_permission(request_user.id, 'facturacion.view', request_user.role):
                flash("No tienes permiso para ver esta factura", "warning")
                abort(403)
        
        # Construir la ruta al PDF
        pdf_filename = f"invoice_{invoice_id}.pdf"
        pdf_dir = Path(__file__).parent.parent / "static" / "invoices"
        pdf_path = pdf_dir / pdf_filename
        
        # Si el PDF no existe, intentar generarlo
        if not pdf_path.exists():
            try:
                import invoice_pdf
                import company
                
                # Preparar datos para generar el PDF
                company_info = company.get_company_info()
                invoice_data = {
                    'id': invoice['id'],
                    'number': invoice.get('number', f"INV-{invoice['id']:04d}"),
                    'issued_date': invoice['issued_date'],
                    'due_date': invoice.get('due_date', ''),
                    'client_name': invoice.get('client_name', ''),
                    'client_address': invoice.get('client_address', ''),
                    'client_phone': invoice.get('client_phone', ''),
                    'client_email': invoice.get('client_email', ''),
                    'items': invoice.get('items', []),
                    'subtotal': invoice.get('subtotal', 0),
                    'tax': invoice.get('tax', 0),
                    'total': invoice.get('total', 0),
                    'notes': invoice.get('notes', ''),
                    'status': invoice.get('status', 'pending')
                }
                
                # Crear directorio si no existe
                pdf_dir.mkdir(parents=True, exist_ok=True)
                
                # Generar el PDF
                invoice_pdf.generate_invoice_pdf(invoice_data, company_info, str(pdf_path))
                
            except Exception as e:
                logger.error(f"Error generando PDF: {e}")
                flash("No se pudo generar el PDF de la factura", "error")
                if request_user.role == 'resident':
                    return redirect(url_for('dashboard'))
                return redirect(url_for('billing.invoices'))
        
        # Servir el archivo PDF
        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=pdf_filename
        )
        
    except Exception as e:
        logger.error(f"Error en view_invoice_pdf: {e}")
        flash("Error al cargar el PDF", "error")
        if request_user.role == 'resident':
            return redirect(url_for('dashboard'))
        return redirect(url_for('billing.invoices'))


# ========== RUTAS ADICIONALES ==========

@billing_bp.route('/facturas/reprint/<int:invoice_id>', methods=['POST'], endpoint='reprint_invoice')
@login_required
@permission_required('facturacion.view')
def reprint_invoice(invoice_id):
    """Reimprimir una factura (regenerar PDF)"""
    try:
        invoice = models.get_invoice_by_id(invoice_id)
        if not invoice:
            flash("Factura no encontrada", "error")
            return redirect(url_for('billing.invoices'))
        
        # Intentar regenerar el PDF
        try:
            import invoice_pdf
            import company
            
            pdf_dir = Path(__file__).parent.parent / "static" / "invoices"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = pdf_dir / f"invoice_{invoice_id}.pdf"
            
            company_info = company.get_company_info()
            
            # Obtener datos del apartamento
            apt = apartments.get_apartment(invoice.get('unit_id'))
            
            invoice_data = {
                'id': invoice['id'],
                'number': f"INV-{invoice['id']:04d}",
                'issued_date': invoice.get('issued_date', ''),
                'due_date': invoice.get('due_date', ''),
                'description': invoice.get('description', ''),
                'amount': invoice.get('amount', 0),
                'client_name': apt.get('resident_name', '') if apt else '',
                'client_address': apt.get('notes', '') if apt else '',
                'client_phone': apt.get('resident_phone', '') if apt else '',
                'client_email': apt.get('resident_email', '') if apt else '',
            }
            
            invoice_pdf.generate_invoice_pdf(invoice_data, company_info, str(pdf_path))
            flash(f"Factura #{invoice_id} reimpresa exitosamente", "success")
            
            # Redirigir al PDF
            return redirect(url_for('billing.view_invoice_pdf', invoice_id=invoice_id))
            
        except Exception as e:
            logger.error(f"Error reimprimiendo factura: {e}")
            flash(f"Error al reimprimir: {e}", "error")
            
    except Exception as e:
        logger.error(f"Error en reprint_invoice: {e}")
        flash(f"Error: {e}", "error")
    
    return redirect(url_for('billing.invoices'))


@billing_bp.route('/facturas/resend/<int:invoice_id>', methods=['POST'], endpoint='resend_invoice')
@login_required
@permission_required('facturacion.view')
def resend_invoice(invoice_id):
    """Reenviar factura por email"""
    try:
        invoice = models.get_invoice_by_id(invoice_id)
        if not invoice:
            flash("Factura no encontrada", "error")
            return redirect(url_for('billing.invoices'))
        
        email = request.form.get('email', '').strip()
        attach_pdf = request.form.get('attach_pdf') == 'on'
        
        if not email:
            flash("Debe proporcionar un email", "error")
            return redirect(url_for('billing.invoices'))
        
        # Validar email basico
        import re
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            flash("El email proporcionado no es valido", "error")
            return redirect(url_for('billing.invoices'))
        
        # Intentar enviar
        try:
            _send_invoice_email(
                invoice,
                client_email=email,
                attach_pdf=attach_pdf,
            )
            flash(f"Factura #{invoice_id} enviada a {email}", "success")
                
        except Exception as e:
            logger.error(f"Error enviando factura: {e}")
            flash(f"Error al enviar: {e}", "error")
            
    except Exception as e:
        logger.error(f"Error en resend_invoice: {e}")
        flash(f"Error: {e}", "error")
    
    return redirect(url_for('billing.invoices'))


# Alias para compatibilidad con template
@billing_bp.route('/facturas/edit/<int:invoice_id>', methods=['GET'], endpoint='edit_invoice')
@login_required
@permission_required('facturacion.edit')
def edit_invoice_redirect(invoice_id):
    """Alias para editar factura - redirige a edit_factura"""
    return redirect(url_for('billing.edit_factura', invoice_id=invoice_id))


# ========== API ENDPOINTS (JSON) para Dashboard Wizards ==========

@billing_bp.route('/api/clients', methods=['GET'])
@login_required
def api_clients():
    """Devuelve lista de clientes (apartamentos con residentes) como JSON."""
    try:
        apts = apartments.list_apartments()
        clients = []
        for a in apts:
            if a.get('resident_name'):
                clients.append({
                    'id': a['id'],
                    'name': a['resident_name'],
                    'apartment': a['number'],
                    'email': a.get('resident_email', ''),
                    'phone': a.get('resident_phone', ''),
                })
        return jsonify({'success': True, 'clients': clients})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@billing_bp.route('/api/services', methods=['GET'])
@login_required
def api_services():
    """Devuelve lista de servicios/productos activos como JSON."""
    try:
        svcs = products_services.list_products_services(active_only=True)
        services = [{'id': s['id'], 'code': s.get('code', ''), 'name': s['name'],
                      'price': s.get('price', 0), 'type': s.get('type', '')} for s in svcs]
        return jsonify({'success': True, 'services': services})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@billing_bp.route('/api/pending-invoices', methods=['GET'])
@login_required
def api_pending_invoices():
    """Devuelve facturas pendientes con balance, opcionalmente filtradas por client_id."""
    try:
        client_id = request.args.get('client_id', type=int)
        
        from data_models.models import Invoice, Apartment, Payment
        from extensions import db as sa_db
        from sqlalchemy import func
        
        # Subquery for total_paid
        paid_subq = sa_db.session.query(
            Payment.invoice_id,
            func.sum(Payment.amount).label('total_paid')
        ).group_by(Payment.invoice_id).subquery()
        
        query = sa_db.session.query(
            Invoice.id,
            Invoice.description,
            Invoice.amount,
            Invoice.issued_date,
            Invoice.due_date,
            Apartment.resident_name.label('client_name'),
            Apartment.number.label('apartment_number'),
            func.coalesce(paid_subq.c.total_paid, 0).label('total_paid')
        ).outerjoin(Apartment, Invoice.unit_id == Apartment.id)\
         .outerjoin(paid_subq, Invoice.id == paid_subq.c.invoice_id)\
         .filter(Invoice.paid == False)
         
        if client_id:
            query = query.filter(Invoice.unit_id == client_id)
            
        query = query.order_by(Invoice.id.desc())
        
        results = query.all()
        rows = []
        for r in results:
            rows.append({
                'id': r.id,
                'description': r.description,
                'amount': r.amount,
                'issued_date': r.issued_date,
                'due_date': r.due_date,
                'client_name': r.client_name,
                'apartment_number': r.apartment_number,
                'total_paid': r.total_paid,
                'remaining': max(r.amount - r.total_paid, 0)
            })
            
        return jsonify({'success': True, 'invoices': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Variable para verificar disponibilidad de senders
try:
    import senders
    HAS_SENDERS = True
except ImportError:
    HAS_SENDERS = False


# ========== COMPROBANTES DE PAGO Y ESTADOS DE CUENTA PARA RESIDENTES ==========

@billing_bp.route('/pagos/pdf/<int:payment_id>', endpoint='view_receipt_pdf')
@login_required
def view_receipt_pdf(payment_id):
    """Ver/descargar PDF de un recibo de pago"""
    try:
        from db import get_conn
        import company
        import receipt_pdf
        
        from data_models.models import Payment, Invoice
        from extensions import db as sa_db
        
        # 1. Obtener datos del pago y su factura
        p_obj = sa_db.session.get(Payment, payment_id)
        
        if p_obj:
            payment = {
                'id': p_obj.id,
                'amount': p_obj.amount,
                'method': p_obj.method,
                'paid_date': p_obj.paid_date,
                'notes': p_obj.notes,
                'invoice_id': p_obj.invoice_id,
                'unit_id': p_obj.invoice.unit_id,
                'invoice_desc': p_obj.invoice.description,
                'invoice_amount': p_obj.invoice.amount
            }
        else:
            payment = None
        
        if not payment:
            flash("Pago no encontrado", "error")
            if current_user.role == 'resident':
                return redirect(url_for('dashboard'))
            return redirect(url_for('billing.payments'))
            
        # 2. Validación de pertenencia si es residente
        if current_user.role == 'resident':
            allowed_unit_ids = _get_resident_allowed_unit_ids()
            if payment['unit_id'] not in allowed_unit_ids:
                flash("Acceso denegado: este recibo no pertenece a su apartamento", "error")
                return redirect(url_for('dashboard'))
        else:
            from utils.permissions import check_permission
            if not check_permission(current_user.id, 'facturacion.view', current_user.role):
                flash("No tienes permiso para ver este recibo", "warning")
                abort(403)
                
        # 3. Obtener el apartamento
        apt = apartments.get_apartment(payment['unit_id'])
        if not apt:
            flash("Apartamento asociado no encontrado", "error")
            return redirect(url_for('dashboard'))
            
        # 4. Formatear la ruta y el nombre del PDF
        apt_number = apt.get('number', 'N/A')
        resident_name = apt.get('resident_name', 'Cliente')
        invoice_num = payment['invoice_id']
        
        # Limpieza simple de caracteres especiales
        safe_resident_name = "".join(c for c in resident_name if c.isalnum() or c in (' ', '_', '-')).strip()
        
        pdf_filename = f"Apartamento {apt_number}-{safe_resident_name}-Comprobante de pago Factura #{invoice_num}.pdf"
        pdf_dir = Path(__file__).parent.parent / "static" / "invoices"
        pdf_path = pdf_dir / pdf_filename
        
        # 5. Generar PDF si no existe en disco
        if not pdf_path.exists():
            try:
                pdf_dir.mkdir(parents=True, exist_ok=True)
                company_info = company.get_company_info() or {}
                
                # Obtener total pagado histórico en esa factura
                from sqlalchemy import func
                total_paid = sa_db.session.query(func.sum(Payment.amount)).filter_by(invoice_id=invoice_num).scalar() or 0.0
                
                payment_data = {
                    'id': payment['id'],
                    'amount': payment['amount'],
                    'method': payment['method'],
                    'payment_date': payment['paid_date'][:10] if payment['paid_date'] else datetime.now().strftime('%Y-%m-%d'),
                    'notes': payment['notes'] or ''
                }
                
                invoice_data = {
                    'id': invoice_num,
                    'description': payment['invoice_desc'],
                    'amount': payment['invoice_amount'],
                    'total_paid': total_paid,
                    'apartment_number': apt_number,
                    'resident_name': resident_name,
                    'resident_email': apt.get('resident_email', '') or '',
                    'resident_phone': apt.get('resident_phone', '') or ''
                }
                
                receipt_pdf.generate_payment_receipt_pdf(payment_data, invoice_data, company_info, str(pdf_path))
            except Exception as e:
                logger.error(f"Error generando PDF de recibo: {e}")
                flash("No se pudo generar el PDF del recibo de pago", "error")
                if current_user.role == 'resident':
                    return redirect(url_for('dashboard'))
                return redirect(url_for('billing.payments'))
                
        # 6. Servir el archivo PDF de forma interactiva
        return send_from_directory(
            pdf_dir,
            pdf_filename,
            as_attachment=True,
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"Error en view_receipt_pdf: {e}")
        flash("Error al cargar el recibo de pago", "error")
        if current_user.role == 'resident':
            return redirect(url_for('dashboard'))
        return redirect(url_for('billing.payments'))


@billing_bp.route('/apartamentos/estado-cuenta/<int:unit_id>', endpoint='download_statement_pdf')
@login_required
def download_statement_pdf(unit_id):
    """Ver o descargar el estado de cuenta actualizado de un apartamento en PDF"""
    try:
        request_user = _get_request_user()
        import apartments
        import company
        from db import get_conn
        import receipt_pdf
        
        # 1. Obtener apartamento
        apt = apartments.get_apartment(unit_id)
        if not apt:
            flash("Apartamento no encontrado", "error")
            return redirect(url_for('dashboard'))
            
        # 2. Validación de pertenencia si es residente
        if request_user.role == 'resident':
            allowed_unit_ids = _get_resident_allowed_unit_ids()
            if unit_id not in allowed_unit_ids:
                flash("Acceso denegado: este apartamento no le pertenece", "error")
                return redirect(url_for('dashboard'))
        else:
            from utils.permissions import check_permission
            if not check_permission(request_user.id, 'apartamentos.view', request_user.role):
                flash("No tienes permiso para ver el estado de cuenta de este apartamento", "warning")
                abort(403)
                
        # 3. Formatear la ruta y el nombre del PDF
        apt_number = apt.get('number', 'N/A')
        resident_name = apt.get('resident_name', 'Cliente')
        safe_resident_name = "".join(c for c in resident_name if c.isalnum() or c in (' ', '_', '-')).strip()
        
        pdf_filename = f"Apartamento {apt_number}-{safe_resident_name}-Estado de cuenta.pdf"
        pdf_dir = Path(__file__).parent.parent / "static" / "invoices"
        pdf_path = pdf_dir / pdf_filename
        
        # 4. Generar el PDF dinámicamente cada vez para contener datos totalmente vigentes
        try:
            pdf_dir.mkdir(parents=True, exist_ok=True)
            
            from data_models.models import Invoice, Payment
            from extensions import db as sa_db
            
            # Obtener facturas para el apartamento (hasta las últimas 20)
            invoices_orm = Invoice.query.filter_by(unit_id=unit_id).order_by(Invoice.issued_date.desc()).limit(20).all()
            invoices = [{
                'id': i.id, 'description': i.description, 'amount': i.amount,
                'issued_date': i.issued_date, 'due_date': i.due_date, 'paid': 1 if i.paid else 0
            } for i in invoices_orm]
            
            # Obtener cobros y abonos para el apartamento (hasta los últimos 20)
            payments_orm = Payment.query.join(Invoice).filter(Invoice.unit_id == unit_id).order_by(Payment.paid_date.desc()).limit(20).all()
            payments = [{
                'id': p.id, 'amount': p.amount, 'paid_date': p.paid_date,
                'method': p.method, 'invoice_id': p.invoice_id
            } for p in payments_orm]
            
            # Calcular balance
            from models import get_balance
            balance = get_balance(unit_id)
            
            company_info = company.get_company_info() or {}
            
            # Generar el PDF
            receipt_pdf.generate_account_statement_pdf(apt, invoices, payments, company_info, str(pdf_path))
        except Exception as e:
            logger.error(f"Error generando PDF de estado de cuenta: {e}")
            flash("No se pudo generar el PDF del estado de cuenta", "error")
            return redirect(url_for('dashboard'))
            
        # 5. Servir el archivo PDF recién generado
        return send_from_directory(
            pdf_dir,
            pdf_filename,
            as_attachment=True,
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"Error en download_statement_pdf: {e}")
        flash("Error al cargar el estado de cuenta", "error")
        return redirect(url_for('dashboard'))

# ========== VISUALIZACIÓN HTML (MÓVILES/PWA) ==========

@billing_bp.route('/facturas/ver-html-v2/<int:invoice_id>', endpoint='view_invoice_html')
@login_required
def view_invoice_html(invoice_id):
    """Ver factura en HTML en vez de PDF (amigable para móviles)"""
    try:
        request_user = _get_request_user()
        invoice = models.get_invoice_by_id(invoice_id)
        if not invoice:
            return "Error: Factura no encontrada", 400
        
        if request_user.role == 'resident':
            allowed_unit_ids = _get_resident_allowed_unit_ids()
            if invoice.get('unit_id') not in allowed_unit_ids:
                return f"Error: Acceso denegado. Unit_id {invoice.get('unit_id')} no esta en {allowed_unit_ids}", 403
        else:
            from utils.permissions import check_permission
            if not check_permission(request_user.id, 'facturacion.view', request_user.role):
                flash("No tienes permiso para ver esta factura", "warning")
                abort(403)
        
        import apartments, company
        apt = apartments.get_apartment(invoice.get('unit_id')) or {}
        company_info = company.get_company_info() or {}
        
        from data_models.models import Payment
        from extensions import db as sa_db
        from sqlalchemy import func
        total_paid = sa_db.session.query(func.sum(Payment.amount)).filter_by(invoice_id=invoice_id).scalar() or 0.0
        invoice['total_paid'] = float(total_paid)
        
        return render_template(
            'resident_document_view.html',
            doc_type='invoice',
            invoice=invoice,
            company_info=company_info,
            resident_name=apt.get('resident_name', invoice.get('client_name', 'Cliente')),
            apt_number=apt.get('number', 'N/A')
        )
    except Exception as e:
        import traceback
        return f"<h3>Error interno al cargar la factura:</h3><pre>{traceback.format_exc()}</pre>", 200

@billing_bp.route('/pagos/ver-html-v2/<int:payment_id>', endpoint='view_receipt_html')
@login_required
def view_receipt_html(payment_id):
    """Ver recibo en HTML en vez de PDF"""
    try:
        from data_models.models import Payment
        from extensions import db as sa_db
        p_obj = sa_db.session.get(Payment, payment_id)
        
        if not p_obj:
            return "Error: Pago no encontrado", 400
            
        payment_dict = {
            'id': p_obj.id, 'amount': p_obj.amount, 'method': p_obj.method,
            'payment_date': (p_obj.paid_date[:10] if isinstance(p_obj.paid_date, str) else p_obj.paid_date.strftime('%Y-%m-%d')) if p_obj.paid_date else datetime.now().strftime('%Y-%m-%d'),
            'notes': p_obj.notes, 'unit_id': p_obj.invoice.unit_id
        }
        
        if current_user.role == 'resident':
            allowed_unit_ids = _get_resident_allowed_unit_ids()
            if payment_dict['unit_id'] not in allowed_unit_ids:
                return f"Error: Acceso denegado al recibo. Unit_id {payment_dict['unit_id']} no esta en {allowed_unit_ids}", 403
        else:
            from utils.permissions import check_permission
            if not check_permission(current_user.id, 'facturacion.view', current_user.role):
                flash("No tienes permiso", "warning")
                abort(403)
                
        import apartments, company
        apt = apartments.get_apartment(payment_dict['unit_id']) or {}
        company_info = company.get_company_info() or {}
        
        invoice = models.get_invoice_by_id(p_obj.invoice_id)
        if not invoice:
            return "Error: Factura asociada no encontrada", 400
        
        invoice_dict = {'id': p_obj.invoice_id, 'description': p_obj.invoice.description, 'amount': p_obj.invoice.amount}
        
        return render_template(
            'resident_document_view.html',
            doc_type='receipt',
            payment=payment_dict,
            invoice=invoice_dict,
            company_info=company_info,
            resident_name=apt.get('resident_name', 'Cliente'),
            apt_number=apt.get('number', 'N/A')
        )
    except Exception as e:
        import traceback
        return f"<h3>Error interno al cargar el recibo:</h3><pre>{traceback.format_exc()}</pre>", 200

@billing_bp.route('/apartamentos/estado-cuenta-html-v2/<int:unit_id>', endpoint='view_statement_html')
@login_required
def view_statement_html(unit_id):
    """Ver estado de cuenta en HTML"""
    try:
        request_user = _get_request_user()
        if request_user.role == 'resident':
            allowed_unit_ids = _get_resident_allowed_unit_ids()
            if unit_id not in allowed_unit_ids:
                flash("Acceso denegado", "error")
                return redirect(url_for('dashboard'))
                
        import apartments, company
        apt = apartments.get_apartment(unit_id)
        if not apt:
            flash("Apartamento no encontrado", "error")
            return redirect(url_for('dashboard'))
            
        from data_models.models import Invoice, Payment
        invoices_orm = Invoice.query.filter_by(unit_id=unit_id).order_by(Invoice.issued_date.desc()).limit(20).all()
        invoices = [{'issued_date': i.issued_date, 'description': i.description, 'amount': i.amount} for i in invoices_orm]
        
        payments_orm = Payment.query.join(Invoice).filter(Invoice.unit_id == unit_id).order_by(Payment.paid_date.desc()).limit(20).all()
        payments = [{'paid_date': p.paid_date, 'method': p.method, 'amount': p.amount} for p in payments_orm]
        
        from models import get_balance
        balance = get_balance(unit_id)
        
        return render_template(
            'resident_document_view.html',
            doc_type='statement',
            invoices=invoices,
            payments=payments,
            balance=balance,
            current_date=datetime.now().strftime('%Y-%m-%d %H:%M'),
            company_info=company.get_company_info() or {},
            resident_name=apt.get('resident_name', 'Cliente'),
            apt_number=apt.get('number', 'N/A')
        )
    except Exception as e:
        import traceback
        return f"<h3>Error interno al cargar el estado de cuenta:</h3><pre>{traceback.format_exc()}</pre>", 200
