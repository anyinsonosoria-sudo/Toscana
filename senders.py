import os
import tempfile
import subprocess
from email.message import EmailMessage
import smtplib
from pathlib import Path

def generate_invoice_html(invoice: dict, unit: dict) -> str:
    # Formatear montos con separadores correctos
    amount_formatted = f"${invoice.get('amount', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    html = f"""
    <html><head><meta charset="utf-8"><title>Factura #{invoice['id']}</title></head>
    <body>
      <h2>Factura #{invoice['id']}</h2>
      <p><strong>Unidad:</strong> {unit.get('number','U'+str(unit.get('id','')))}<br>
         <strong>Propietario:</strong> {unit.get('owner','')}<br>
         <strong>Emitida:</strong> {invoice.get('issued_date','')}<br>
         <strong>Vence:</strong> {invoice.get('due_date','')}</p>
      <h3>{invoice.get('description','')}</h3>
      <p><strong>Monto:</strong> {amount_formatted}</p>
      <hr>
      <p>Gracias.</p>
    </body></html>
    """
    return html

def _maybe_make_pdf(html: str) -> bytes:
    wk = os.getenv("WKHTMLTOPDF")
    if not wk:
        return None
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(html)
        html_path = f.name
    pdf_fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
    os.close(pdf_fd)
    try:
        subprocess.check_call([wk, html_path, pdf_path])
        with open(pdf_path, "rb") as pf:
            data = pf.read()
        return data
    except Exception:
        return None
    finally:
        try:
            os.remove(html_path)
        except Exception:
            pass
        try:
            os.remove(pdf_path)
        except Exception:
            pass

def send_email(to_email, subject: str, html: str, attach_pdf=None, attachments=None):
    """
    Envía email con soporte para múltiples destinatarios y adjuntos
    
    Args:
        to_email: Email o lista de emails
        subject: Asunto del email
        html: Contenido HTML
        attach_pdf: Datos del PDF en bytes (legacy support)
        attachments: Lista de rutas de archivos a adjuntar
    """
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    passwd = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("SMTP_FROM", user or "no-reply@example.com")
    
    if not host:
        raise RuntimeError("SMTP_HOST not configured")
    
    msg = EmailMessage()
    msg["From"] = from_addr
    
    # Manejar múltiples destinatarios
    if isinstance(to_email, list):
        msg["To"] = ", ".join(to_email)
    else:
        msg["To"] = to_email
    
    msg["Subject"] = subject
    msg.set_content("Versión HTML disponible")
    msg.add_alternative(html, subtype="html")
    
    # Adjuntar PDF en bytes (legacy)
    if attach_pdf:
        msg.add_attachment(attach_pdf, maintype="application", subtype="pdf", filename="factura.pdf")
    
    # Adjuntar archivos desde rutas
    if attachments:
        for attachment in attachments:
            # Soportar tanto tuplas (ruta, nombre) como strings (solo ruta)
            if isinstance(attachment, tuple):
                attachment_path, file_name = attachment
            else:
                attachment_path = attachment
                file_name = Path(attachment_path).name
            
            if Path(attachment_path).exists():
                with open(attachment_path, 'rb') as f:
                    file_data = f.read()
                    msg.add_attachment(file_data, maintype="application", subtype="pdf", filename=file_name)
    
    # Conectar y enviar
    if port == 465:
        smtp = smtplib.SMTP_SSL(host, port)
    else:
        smtp = smtplib.SMTP(host, port)
        smtp.starttls()
    try:
        if user and passwd:
            smtp.login(user, passwd)
        smtp.send_message(msg)
    finally:
        smtp.quit()

def send_sms_via_twilio(to_number: str, body: str):
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM")
    if not (sid and token and from_number):
        raise RuntimeError("TWILIO credentials not configured")
    # do a simple requests POST if requests is available
    try:
        import requests
    except Exception:
        raise RuntimeError("requests required for Twilio SMS (pip install requests)")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    resp = requests.post(url, data={"From": from_number, "To": to_number, "Body": body},
                         auth=(sid, token))
    if not resp.ok:
        raise RuntimeError(f"Twilio error: {resp.status_code} {resp.text}")

def send_whatsapp_via_twilio(to_number: str, body: str):
    """Envía mensaje por WhatsApp usando Twilio"""
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_whatsapp = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # Número sandbox por defecto
    
    if not (sid and token):
        raise RuntimeError("TWILIO credentials not configured")
    
    try:
        import requests
    except Exception:
        raise RuntimeError("requests required for Twilio (pip install requests)")
    
    # Asegurar formato WhatsApp
    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"
    if not from_whatsapp.startswith("whatsapp:"):
        from_whatsapp = f"whatsapp:{from_whatsapp}"
    
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    resp = requests.post(url, 
                        data={"From": from_whatsapp, "To": to_number, "Body": body},
                        auth=(sid, token))
    if not resp.ok:
        raise RuntimeError(f"Twilio WhatsApp error: {resp.status_code} {resp.text}")

def generate_payment_notification_html(payment: dict, invoice: dict, unit: dict, is_admin: bool = False) -> str:
    """Genera el HTML para la notificación de pago"""
    
    # Formatear montos
    def format_amount(val):
        return f"RD${val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #28a745; color: white; padding: 20px; text-align: center; border-radius: 8px; }}
            .content {{ background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; }}
            .detail {{ margin: 10px 0; padding: 8px; background: white; border-radius: 4px; }}
            .amount {{ color: #28a745; font-weight: bold; font-size: 18px; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; padding: 20px; margin-top: 30px; border-top: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>✓ Pago Registrado Exitosamente</h2>
            </div>
            <div class="content">
                <p>{'Estimado Administrador' if is_admin else 'Estimado Cliente'},</p>
                <p>Se ha registrado un pago con los siguientes detalles:</p>
                
                <div class="detail"><strong>Factura #:</strong> {invoice['id']}</div>
                <div class="detail"><strong>Unidad:</strong> {unit.get('number', 'N/A')}</div>
                <div class="detail"><strong>Descripción:</strong> {invoice.get('description', 'N/A')}</div>
                <div class="detail"><strong>Monto Factura:</strong> {format_amount(invoice.get('amount', 0))}</div>
                <div class="detail"><strong>Monto Pagado:</strong> <span class="amount">{format_amount(payment.get('amount', 0))}</span></div>
                <div class="detail"><strong>Método de Pago:</strong> {payment.get('method', 'N/A').capitalize()}</div>
                <div class="detail"><strong>Fecha de Pago:</strong> {payment.get('payment_date', 'N/A')}</div>
            </div>
            <div class="footer">
                <p>Este es un mensaje automático. Por favor no responda a este correo.</p>
                <p>Si tiene alguna pregunta, contáctenos directamente.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_payment_notification(payment: dict, invoice: dict, unit: dict, client_email: str = None, admin_email: str = None, 
                            receipt_path: str = None, account_statement_path: str = None, client_phone: str = None):
    """
    Envía notificaciones de pago al cliente y al administrador con comprobantes adjuntos
    
    Args:
        payment: Datos del pago
        invoice: Datos de la factura
        unit: Datos del apartamento/unidad
        client_email: Email del cliente (opcional)
        admin_email: Email del administrador (opcional)
        receipt_path: Ruta del comprobante de pago PDF (opcional)
        account_statement_path: Ruta del estado de cuenta PDF (opcional)
        client_phone: Teléfono del cliente para WhatsApp (opcional)
    """
    
    # Preparar adjuntos con nombres descriptivos
    attachments = []
    if receipt_path and Path(receipt_path).exists():
        # Usar el nombre original del archivo que ya tiene el formato correcto
        attachments.append((receipt_path, Path(receipt_path).name))
    if account_statement_path and Path(account_statement_path).exists():
        # Usar el nombre original del archivo que ya tiene el formato correcto
        attachments.append((account_statement_path, Path(account_statement_path).name))

    # --- LOGGING: Log client email before sending ---
    print(f"[DEBUG] Attempting to send payment notification to client. Email: '{client_email}' | Invoice ID: {invoice.get('id')} | Payment ID: {payment.get('id')}")

    # --- VALIDATION: Check if client_email is valid ---
    import re
    def is_valid_email(email):
        if not email or not isinstance(email, str):
            return False
        # Simple regex for email validation
        return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None

    if client_email:
        if not is_valid_email(client_email):
            print(f"[ERROR] Invalid or empty client email: '{client_email}' (Invoice ID: {invoice.get('id')})")
        else:
            try:
                html = generate_payment_notification_html(payment, invoice, unit, is_admin=False)
                subject = f"Confirmación de Pago - Factura #{invoice['id']}"
                # Incluir comprobante y estado de cuenta para el cliente
                send_email(client_email, subject, html, attachments=attachments if attachments else None)
                print(f"✓ Comprobante de pago enviado al cliente: {client_email}")
            except Exception as e:
                # Log error but don't fail the whole operation
                print(f"✗ Error sending payment notification to client: {e}")
    else:
        print(f"[ERROR] No client email provided for payment notification. Invoice ID: {invoice.get('id')}, Payment ID: {payment.get('id')}")

    # Enviar WhatsApp al cliente
    if client_phone:
        send_payment_whatsapp(payment, invoice, unit, client_phone)
    
    # Enviar email al administrador
    if admin_email:
        try:
            html = generate_payment_notification_html(payment, invoice, unit, is_admin=True)
            subject = f"Notificación de Pago Recibido - Factura #{invoice['id']} - Unidad {unit.get('number', 'N/A')}"
            
            # Solo incluir comprobante para el administrador (no estado de cuenta)
            admin_attachments = [(receipt_path, Path(receipt_path).name)] if receipt_path and Path(receipt_path).exists() else None
            send_email(admin_email, subject, html, attachments=admin_attachments)
            print(f"✓ Notificación de pago enviada al administrador: {admin_email}")
        except Exception as e:
            # Log error but don't fail the whole operation
            print(f"✗ Error sending payment notification to admin: {e}")
def generate_account_statement_html(unit: dict, invoices: list, payments: list, balance: float) -> str:
    """Genera el HTML para el estado de cuenta"""
    
    # Calcular totales
    total_invoiced = sum(inv.get('amount', 0) for inv in invoices)
    total_paid = sum(pay.get('amount', 0) for pay in payments)
    
    # Función para formatear montos
    def format_amount(val):
        return f"RD${val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    # Generar lista de facturas
    invoices_html = ""
    for inv in invoices:
        status = "Pagada" if inv.get('paid') else "Pendiente"
        status_color = "#28a745" if inv.get('paid') else "#ffc107"
        invoices_html += f"""
        <tr>
            <td>#{inv.get('id', 'N/A')}</td>
            <td>{inv.get('issued_date', 'N/A')}</td>
            <td>{inv.get('description', 'N/A')}</td>
            <td>{format_amount(inv.get('amount', 0))}</td>
            <td><span style="color: {status_color}; font-weight: bold;">{status}</span></td>
        </tr>
        """
    
    # Generar lista de pagos
    payments_html = ""
    for pay in payments:
        payments_html += f"""
        <tr>
            <td>{pay.get('paid_date', 'N/A')}</td>
            <td>#{pay.get('invoice_id', 'N/A')}</td>
            <td>{pay.get('method', 'N/A').capitalize()}</td>
            <td style="color: #28a745; font-weight: bold;">{format_amount(pay.get('amount', 0))}</td>
        </tr>
        """
    
    # Obtener información del residente
    resident = unit.get('resident', {})
    
    # Generar HTML completo
    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Estado de Cuenta</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #007bff; color: white; padding: 30px; text-align: center; }}
            .resident-info {{ background: #f8f9fa; padding: 15px; margin-bottom: 20px; border-radius: 8px; }}
            .section {{ margin: 20px 0; }}
            .section-title {{ background: #f8f9fa; padding: 10px; border-left: 4px solid #007bff; margin-bottom: 15px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f8f9fa; font-weight: bold; }}
            .summary {{ background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; }}
            .summary-item {{ display: flex; justify-content: space-between; margin: 10px 0; }}
            .balance {{ font-size: 24px; color: {('#dc3545' if balance > 0 else '#28a745')}; font-weight: bold; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; padding: 20px; margin-top: 30px; border-top: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Estado de Cuenta</h1>
                <h3>Apartamento {unit.get('number', 'N/A')}</h3>
            </div>
            
            <div class="resident-info">
                <p><strong>Residente:</strong> {resident.get('name', 'N/A')}</p>
                <p><strong>Email:</strong> {resident.get('email', 'N/A')}</p>
                <p><strong>Teléfono:</strong> {resident.get('phone', 'N/A')}</p>
                <p><strong>Rol:</strong> {resident.get('role_other') if resident.get('role') == 'Otro' else resident.get('role', 'N/A')}</p>
                <p><strong>Términos de pago:</strong> {resident.get('payment_terms', 'N/A')} días</p>
            </div>
            
            <div class="summary">
                <div class="summary-item">
                    <span><strong>Total Facturado:</strong></span>
                    <span>{format_amount(total_invoiced)}</span>
                </div>
                <div class="summary-item">
                    <span><strong>Total Pagado:</strong></span>
                    <span style="color: #28a745;">{format_amount(total_paid)}</span>
                </div>
                <div class="summary-item" style="border-top: 2px solid #333; padding-top: 10px; margin-top: 10px;">
                    <span><strong>Balance {'Pendiente' if balance > 0 else 'Disponible'}:</strong></span>
                    <span class="balance">{format_amount(abs(balance))}</span>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">
                    <h3 style="margin: 0;">Facturas</h3>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Factura</th>
                            <th>Fecha</th>
                            <th>Descripción</th>
                            <th>Monto</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        {invoices_html if invoices_html else '<tr><td colspan=\"5\" style=\"text-align: center; color: #999;\">No hay facturas registradas</td></tr>'}
                    </tbody>
                </table>
            </div>
            
            <div class=\"section\">
                <div class=\"section-title\">
                    <h3 style=\"margin: 0;\">Pagos Realizados</h3>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Fecha</th>
                            <th>Factura</th>
                            <th>Método</th>
                            <th>Monto</th>
                        </tr>
                    </thead>
                    <tbody>
                        {payments_html if payments_html else '<tr><td colspan=\"4\" style=\"text-align: center; color: #999;\">No hay pagos registrados</td></tr>'}
                    </tbody>
                </table>
            </div>
            
            <div class=\"footer\">
                <p>Este es un estado de cuenta generado automáticamente.</p>
                <p>Si tiene alguna pregunta, contáctenos directamente.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_account_statement(unit: dict, invoices: list, payments: list, balance: float, client_email: str):
    """Envía el estado de cuenta por email al cliente"""
    html = generate_account_statement_html(unit, invoices, payments, balance)
    subject = f"Estado de Cuenta - Unidad {unit.get('number', 'N/A')}"
    send_email(client_email, subject, html)

def send_invoice_notification(invoice, unit, client_email=None, admin_email=None, attach_pdf=False, pdf_path=None, client_phone=None):
    """
    Envía notificación de factura por email y WhatsApp
    
    Args:
        invoice: Dict con datos de la factura
        unit: Dict con datos de la unidad
        client_email: Email del cliente
        admin_email: Email del administrador
        attach_pdf: Si se debe adjuntar el PDF
        pdf_path: Ruta al archivo PDF (opcional)
        client_phone: Teléfono del cliente para WhatsApp (opcional)
    """
    from pathlib import Path
    
    resident_name = invoice.get('resident_name', 'Cliente')
    unit_number = unit.get('number', 'N/A')
    invoice_id = invoice.get('id', '')
    
    subject = f"{resident_name} - Apartamento {unit_number} - Factura #{invoice_id}"
    
    # Formatear montos con separadores correctos
    amount_formatted = f"RD${invoice['amount']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    body = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #007bff; color: white; padding: 20px; text-align: center; border-radius: 8px; }}
            .content {{ background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; }}
            .detail {{ margin: 10px 0; padding: 8px; background: white; border-radius: 4px; }}
            .amount {{ color: #007bff; font-weight: bold; font-size: 20px; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; padding: 20px; margin-top: 30px; border-top: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Nueva Factura Generada</h2>
            </div>
            <div class="content">
                <p>Estimado Cliente,</p>
                <p>Se ha generado una nueva factura con los siguientes detalles:</p>
                
                <div class="detail"><strong>Número de Factura:</strong> #{invoice['id']}</div>
                <div class="detail"><strong>Apartamento:</strong> {unit.get('number', 'N/A')}</div>
                <div class="detail"><strong>Descripción:</strong> {invoice.get('description', 'N/A')}</div>
                <div class="detail"><strong>Monto:</strong> <span class="amount">{amount_formatted}</span></div>
                <div class="detail"><strong>Fecha de Emisión:</strong> {invoice.get('issued_date', 'N/A')}</div>
                <div class="detail"><strong>Fecha de Vencimiento:</strong> {invoice.get('due_date', 'N/A')}</div>
            </div>
            <div class="footer">
                <p>Por favor, realice el pago antes de la fecha de vencimiento.</p>
                <p>Este es un mensaje automático. Por favor no responda a este correo.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    attachments = []
    if attach_pdf and pdf_path:
        # Usar el nombre original del archivo que ya tiene el formato correcto
        if Path(pdf_path).exists():
            attachments.append((str(pdf_path), Path(pdf_path).name))
    elif attach_pdf:
        # Si no se proporciona ruta pero se solicita PDF, buscar en la ubicación por defecto
        default_pdf = Path(__file__).parent / "static" / "invoices" / f"invoice_{invoice['id']}.pdf"
        if default_pdf.exists():
            attachments.append((str(default_pdf), Path(default_pdf).name))
    
    recipients = []
    if client_email:
        recipients.append(client_email)
    if admin_email:
        recipients.append(admin_email)
    
    print(f"\n[SENDERS] send_invoice_notification llamado:")
    print(f"  - Recipients: {recipients}")
    print(f"  - Attachments: {len(attachments)} archivo(s)")
    print(f"  - Subject: {subject}")
    
    if recipients:
        print(f"  🚀 Enviando email a {len(recipients)} destinatario(s)...")
        try:
            send_email(recipients, subject, body, attachments=attachments)
            print(f"  ✅ Email enviado exitosamente!")
        except Exception as e:
            print(f"  ❌ Error enviando email: {e}")
            import traceback
            traceback.print_exc()
            raise
    else:
        print(f"  ⚠️ No hay destinatarios, email NO enviado")
    
    # Enviar por WhatsApp si se proporciona teléfono
    if client_phone:
        send_invoice_whatsapp(invoice, unit, client_phone)

# ========== FUNCIONES DE WHATSAPP ==========

def send_invoice_whatsapp(invoice: dict, unit: dict, client_phone: str = None):
    """
    Envía notificación de factura por WhatsApp
    
    Args:
        invoice: Datos de la factura
        unit: Datos del apartamento/unidad
        client_phone: Teléfono del cliente en formato internacional (+1XXXXXXXXXX)
    """
    if not client_phone:
        return
    
    # Formatear monto
    amount = f"RD${invoice.get('amount', 0):,.2f}"
    
    message = f"""📄 *NUEVA FACTURA*

🏠 Apartamento: {unit.get('number', 'N/A')}
📋 Factura #: {invoice.get('id', 'N/A')}
📅 Fecha emisión: {invoice.get('issued_date', 'N/A')}
📅 Vencimiento: {invoice.get('due_date', 'N/A')}

💼 Descripción:
{invoice.get('description', 'N/A')}

💰 Monto: {amount}

Por favor, realice el pago antes de la fecha de vencimiento.

_Mensaje automático - No responder_"""
    
    try:
        send_whatsapp_via_twilio(client_phone, message)
        print(f"✓ Factura enviada por WhatsApp a {client_phone}")
    except Exception as e:
        print(f"✗ Error enviando factura por WhatsApp: {e}")

def send_payment_whatsapp(payment: dict, invoice: dict, unit: dict, client_phone: str = None):
    """
    Envía notificación de pago recibido por WhatsApp
    
    Args:
        payment: Datos del pago
        invoice: Datos de la factura relacionada
        unit: Datos del apartamento/unidad
        client_phone: Teléfono del cliente en formato internacional (+1XXXXXXXXXX)
    """
    if not client_phone:
        return
    
    # Formatear monto
    amount = f"RD${payment.get('amount', 0):,.2f}"
    method = payment.get('method', 'Efectivo').capitalize()
    
    message = f"""✅ *PAGO RECIBIDO*

🏠 Apartamento: {unit.get('number', 'N/A')}
🧾 Recibo #: {payment.get('id', 'N/A')}
📋 Factura #: {invoice.get('id', 'N/A')}
📅 Fecha: {payment.get('payment_date', 'N/A')}
💳 Método: {method}

💰 Monto Pagado: {amount}

¡Gracias por su pago puntual!

_Mensaje automático - No responder_"""
    
    try:
        send_whatsapp_via_twilio(client_phone, message)
        print(f"✓ Comprobante de pago enviado por WhatsApp a {client_phone}")
    except Exception as e:
        print(f"✗ Error enviando comprobante por WhatsApp: {e}")

def send_statement_whatsapp(unit: dict, invoices: list, payments: list, balance: float, client_phone: str = None):
    """
    Envía estado de cuenta por WhatsApp
    
    Args:
        unit: Datos del apartamento/unidad
        invoices: Lista de facturas
        payments: Lista de pagos
        balance: Balance actual
        client_phone: Teléfono del cliente en formato internacional (+1XXXXXXXXXX)
    """
    if not client_phone:
        return
    
    # Calcular totales
    total_invoiced = sum(inv.get('amount', 0) for inv in invoices)
    total_paid = sum(pay.get('amount', 0) for pay in payments)
    
    # Formatear montos
    balance_text = f"RD${balance:,.2f}"
    total_invoiced_text = f"RD${total_invoiced:,.2f}"
    total_paid_text = f"RD${total_paid:,.2f}"
    
    # Indicador de estado
    if balance > 0:
        status = "⚠️ PENDIENTE DE PAGO"
    elif balance < 0:
        status = "💰 SALDO A FAVOR"
    else:
        status = "✅ AL DÍA"
    
    message = f"""📊 *ESTADO DE CUENTA*

🏠 Apartamento: {unit.get('number', 'N/A')}
👤 Residente: {unit.get('resident_name', 'N/A')}

📋 Total Facturado: {total_invoiced_text}
💵 Total Pagado: {total_paid_text}
💰 Balance: {balance_text}

{status}

📄 Facturas: {len(invoices)}
🧾 Pagos: {len(payments)}

Para ver el detalle completo, revise su email.

_Mensaje automático - No responder_"""
    
    try:
        send_whatsapp_via_twilio(client_phone, message)
        print(f"✓ Estado de cuenta enviado por WhatsApp a {client_phone}")
    except Exception as e:
        print(f"✗ Error enviando estado de cuenta por WhatsApp: {e}")
