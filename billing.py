"""
Módulo de facturación para el sistema de administración de edificios.
"""
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Optional

import db

logger = logging.getLogger(__name__)


def format_currency(amount):
    """Formatea montos con separadores correctos: RD$ 1,000.00"""
    if amount is None:
        amount = 0
    return f"RD$ {amount:,.2f}"


def _get_apartment(unit_id: int) -> dict:
    """Obtiene información del apartamento."""
    import apartments
    apt = apartments.get_apartment(unit_id)
    if not apt:
        raise ValueError(f"Apartamento {unit_id} no encontrado")
    return apt


def _get_service(service_code: str):
    """Obtiene información de un servicio."""
    try:
        import products_services
        return products_services.find_by_code(service_code)
    except Exception as e:
        logger.warning(f"Servicio no encontrado: {service_code} - {e}")
        return None


def _calculate_payment_terms(apt: dict) -> int:
    """Calcula los días de pago desde el apartamento."""
    try:
        terms = int(apt.get('payment_terms', 30))
        return terms if terms > 0 else 30
    except (ValueError, TypeError):
        return 30


def create_invoice_with_lines(
    resident_id,
    service_codes,
    quantities,
    amounts,
    descriptions,
    notify_email=None,
    notify_phone=None,
    attach_pdf=False
):
    """
    Crea una factura con múltiples líneas de servicio.
    
    Args:
        resident_id: ID del apartamento/unidad (unit_id)
        service_codes: Lista de códigos de servicio
        quantities: Lista de cantidades
        amounts: Lista de montos unitarios
        descriptions: Lista de descripciones adicionales
        notify_email: Email para notificación
        notify_phone: Teléfono para WhatsApp (opcional)
        attach_pdf: Si se debe adjuntar PDF al email
        
    Returns:
        ID de la factura creada
    """
    import company
    
    unit_id = resident_id
    
    # Verificar que el apartamento existe
    apt = _get_apartment(unit_id)
    resident_name = apt.get('resident_name', 'Sin nombre')
    payment_terms = _calculate_payment_terms(apt)
    
    # Calcular monto total y construir descripción
    total_amount = 0.0
    description_lines = []
    
    for i, service_code in enumerate(service_codes):
        try:
            qty = float(quantities[i]) if i < len(quantities) else 1.0
            amt = float(amounts[i]) if i < len(amounts) else 0.0
            desc = descriptions[i] if i < len(descriptions) else ""
            
            line_total = qty * amt
            total_amount += line_total
            
            # Buscar nombre del servicio
            service = _get_service(service_code)
            service_name = service['name'] if service else service_code
            
            # Construir línea de descripción
            line_desc = f"{service_name}"
            if desc:
                line_desc += f" - {desc}"
            if qty != 1:
                line_desc += f" (x{qty})"
            
            description_lines.append(line_desc)
        except (ValueError, IndexError) as e:
            logger.warning(f"Error procesando línea {i}: {e}")
            continue
    
    # Descripción completa
    full_description = "\n".join(description_lines)
    
    # Calcular fecha de vencimiento
    issued_date = datetime.now().strftime("%Y-%m-%d")
    due_date = (datetime.now() + timedelta(days=payment_terms)).strftime("%Y-%m-%d")
    
    # Insertar factura en la base de datos
    conn = db.get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO invoices (unit_id, description, amount, issued_date, due_date, paid)
        VALUES (?, ?, ?, ?, ?, 0)
    """, (unit_id, full_description, total_amount, issued_date, due_date))
    
    conn.commit()
    invoice_id = cur.lastrowid
    conn.close()
    
    # Generar PDF si se solicita
    if invoice_id:
        try:
            from company import get_company_info
            import invoice_pdf
            
            company_info = get_company_info()
            pdf_dir = Path(__file__).parent / "static" / "invoices"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            # Nombre formato: Apartamento 4A-Anyinson Osoria-Factura #2
            apt_number = apt.get('number', 'N/A')
            pdf_filename = f"Apartamento {apt_number}-{resident_name}-Factura #{invoice_id}.pdf"
            pdf_path = str(pdf_dir / pdf_filename)
            
            invoice_data = {
                'id': invoice_id,
                'description': full_description,
                'amount': total_amount,
                'issued_date': issued_date,
                'due_date': due_date,
                'apartment_number': apt.get('number', 'N/A'),
                'resident_name': resident_name,
                'resident_phone': apt.get('resident_phone', ''),
                'resident_email': apt.get('resident_email', '')
            }
            
            # Generar PDF (solo 2 argumentos: invoice_data y output_path)
            invoice_pdf.generate_invoice(invoice_data, pdf_path)
            logger.info(f"PDF generated: {pdf_path}")
            
            # Enviar notificaciones al cliente Y al administrador
            try:
                import senders
                
                # Obtener email del administrador desde company_info
                admin_email = company_info.get('email') if company_info else None
                
                print(f"\n{'='*60}")
                print(f"DEBUG: Preparando envío de factura #{invoice_id}")
                print(f"  - Cliente email: {notify_email or 'NO CONFIGURADO'}")
                print(f"  - Admin email: {admin_email or 'NO CONFIGURADO'}")
                print(f"  - PDF path: {pdf_path}")
                print(f"  - PDF existe: {Path(pdf_path).exists()}")
                print(f"{'='*60}\n")
                
                # Preparar datos para envío
                invoice_dict = {
                    'id': invoice_id,
                    'amount': total_amount,
                    'description': full_description,
                    'issued_date': issued_date,
                    'due_date': due_date,
                    'resident_name': resident_name
                }
                
                unit_dict = {
                    'number': apt.get('number', 'N/A'),
                    'id': unit_id
                }
                
                # Enviar a cliente y admin (si se proporcionaron emails)
                # SIEMPRE enviar si hay emails, con o sin PDF
                if notify_email or admin_email:
                    print(f"🚀 EJECUTANDO send_invoice_notification...")
                    senders.send_invoice_notification(
                        invoice_dict,
                        unit_dict,
                        client_email=notify_email,
                        admin_email=admin_email,
                        attach_pdf=True,  # Siempre adjuntar PDF
                        pdf_path=pdf_path,  # Siempre incluir ruta
                        client_phone=notify_phone
                    )
                    
                    recipients = []
                    if notify_email:
                        recipients.append(f"cliente ({notify_email})")
                    if admin_email:
                        recipients.append(f"admin ({admin_email})")
                    
                    print(f"✅ Notificaciones enviadas a: {', '.join(recipients)}")
                    logger.info(f"Notifications sent for invoice {invoice_id} to: {', '.join(recipients)}")
                else:
                    print(f"⚠️ NO SE ENVIÓ: No hay emails configurados")
                    logger.info(f"No emails configured for invoice {invoice_id}")
                    
            except Exception as e:
                print(f"❌ ERROR enviando notificaciones: {e}")
                import traceback
                traceback.print_exc()
                logger.warning(f"Could not send notifications: {e}")
                    
        except Exception as e:
            logger.error(f"Error generating PDF or sending notifications: {e}")
    
    return invoice_id
