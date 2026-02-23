"""
Blueprint para Facturación y Pagos (Billing)
Gestión completa de facturas, pagos, cuentas por cobrar y ventas recurrentes
"""
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import login_required
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
            SELECT p.*, i.description as invoice_desc, i.unit_id, i.amount as invoice_amount
            FROM payments p
            JOIN invoices i ON p.invoice_id = i.id
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
@csrf.exempt
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

@billing_bp.route('/pagos/delete/<int:payment_id>', methods=['POST'])
@login_required
@permission_required('facturacion.delete')
@audit_log('facturacion.eliminar_pago', 'Eliminar pago')
def delete_payment(payment_id):
    """Eliminar un pago registrado"""
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        
        # Obtener información del pago antes de eliminarlo
        cur.execute("SELECT invoice_id, amount FROM payments WHERE id = ?", (payment_id,))
        payment = cur.fetchone()
        
        if payment:
            invoice_id = payment['invoice_id']
            payment_amount = payment['amount']
            
            # Eliminar el pago
            cur.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
            conn.commit()
            
            # Actualizar el estado de la factura
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) as total_paid
                FROM payments
                WHERE invoice_id = ?
            """, (invoice_id,))
            result = cur.fetchone()
            total_paid = result['total_paid'] if result else 0
            
            cur.execute("SELECT amount FROM invoices WHERE id = ?", (invoice_id,))
            invoice = cur.fetchone()
            
            if invoice:
                invoice_amount = invoice['amount']
                is_paid = total_paid >= invoice_amount
                
                cur.execute("""
                    UPDATE invoices 
                    SET paid = ?,
                        pending_amount = ?
                    WHERE id = ?
                """, (is_paid, invoice_amount - total_paid, invoice_id))
                conn.commit()
            
            conn.close()
            flash(f"Pago #{payment_id} eliminado correctamente", "success")
            cache.clear()
        else:
            flash(f"Pago #{payment_id} no encontrado", "error")
            
    except Exception as e:
        flash(f"Error al eliminar pago: {str(e)}", "error")
    
    return redirect(url_for("billing.register_payment"))


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
        conn = db.get_conn()
        cur = conn.cursor()
        
        # Crear venta recurrente (usar unit_id en lugar de resident_id)
        cur.execute("""
            INSERT INTO recurring_sales 
            (unit_id, service_id, amount, frequency, billing_day, billing_time, start_date, end_date, 
             description, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (resident_id, service_id, amount, frequency, billing_day, billing_time, start_date, 
              end_date if end_date else None, description, active))
        sale_id = cur.lastrowid
        conn.commit()
        conn.close()
        
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
@permission_required('facturacion.view')
def view_invoice_pdf(invoice_id):
    """Ver/descargar PDF de una factura"""
    try:
        # Verificar que la factura existe
        invoice = models.get_invoice_by_id(invoice_id)
        if not invoice:
            flash("Factura no encontrada", "error")
            return redirect(url_for('billing.invoices'))
        
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
                return redirect(url_for('billing.invoices'))
        
        # Servir el archivo PDF
        return send_from_directory(
            pdf_dir,
            pdf_filename,
            as_attachment=False,  # False = mostrar en navegador, True = descargar
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error en view_invoice_pdf: {e}")
        flash("Error al cargar el PDF", "error")
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
            if HAS_SENDERS:
                apt = apartments.get_apartment(invoice.get('unit_id'))
                unit_dict = {'id': apt.get('id') if apt else None, 'number': apt.get('number', 'N/A') if apt else 'N/A'}
                
                pdf_path = None
                if attach_pdf:
                    pdf_file = Path(__file__).parent.parent / "static" / "invoices" / f"invoice_{invoice_id}.pdf"
                    if pdf_file.exists():
                        pdf_path = str(pdf_file)
                
                import senders
                senders.send_invoice_notification(invoice, unit_dict, email, pdf_path=pdf_path)
                flash(f"Factura #{invoice_id} enviada a {email}", "success")
            else:
                flash("El modulo de envio no esta disponible", "warning")
                
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
def api_pending_invoices():
    """Devuelve facturas pendientes con balance, opcionalmente filtradas por client_id."""
    try:
        client_id = request.args.get('client_id', type=int)
        conn = db.get_conn()
        cur = conn.cursor()
        query = """
            SELECT i.id, i.description, i.amount, i.issued_date, i.due_date,
                   a.resident_name as client_name, a.number as apartment_number,
                   COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as total_paid
            FROM invoices i
            LEFT JOIN apartments a ON i.unit_id = a.id
            WHERE i.paid = 0
        """
        params = []
        if client_id:
            query += " AND i.unit_id = ?"
            params.append(client_id)
        query += " ORDER BY i.id DESC"
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        for r in rows:
            r['remaining'] = max(r['amount'] - r['total_paid'], 0)
        return jsonify({'success': True, 'invoices': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Variable para verificar disponibilidad de senders
try:
    import senders
    HAS_SENDERS = True
except ImportError:
    HAS_SENDERS = False
