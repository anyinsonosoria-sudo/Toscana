"""
Módulo para generar recibos de pago y estados de cuenta en PDF
Diseño moderno y compacto con esquema marrón/blanco
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime
from pathlib import Path
import io

# ===== Color Palette =====
BROWN       = colors.HexColor('#795548')
BROWN_DARK  = colors.HexColor('#5D4037')
BROWN_LIGHT = colors.HexColor('#D7CCC8')
BROWN_BG    = colors.HexColor('#EFEBE9')
WHITE       = colors.white
TEXT_DARK   = colors.HexColor('#3E2723')
TEXT_MID    = colors.HexColor('#6D4C41')
TEXT_LIGHT  = colors.HexColor('#8D6E63')
GREEN_OK    = colors.HexColor('#2E7D32')
RED_DANGER  = colors.HexColor('#C62828')


def _fmt(amount):
    """Formatea RD$ 1,000.00"""
    return f"RD$ {float(amount or 0):,.2f}"


def _fecha(dt_str=None):
    """Convierte fecha a formato español"""
    meses = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
             'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    try:
        if dt_str:
            d = datetime.strptime(str(dt_str)[:10], '%Y-%m-%d')
        else:
            d = datetime.now()
        return f"{d.day} de {meses[d.month-1]} de {d.year}"
    except:
        return str(dt_str or '')


def _get_logo(company_info):
    """Devuelve Image object o None"""
    if not company_info or not company_info.get('logo_path'):
        return None
    logo_path = Path(__file__).parent / 'static' / 'uploads' / company_info['logo_path']
    if logo_path.exists():
        try:
            return Image(str(logo_path), width=0.9*inch, height=0.9*inch, kind='proportional')
        except:
            pass
    return None


# ============================================================
#  RECIBO DE PAGO
# ============================================================
def generate_payment_receipt_pdf(payment_data, invoice_data, company_info, output_path=None):
    """Genera un comprobante de pago compacto y moderno"""
    
    if output_path:
        doc = SimpleDocTemplate(output_path, pagesize=letter,
                                rightMargin=0.6*inch, leftMargin=0.6*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
    else:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=0.6*inch, leftMargin=0.6*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    story = []
    styles = getSampleStyleSheet()
    W = 6.8 * inch  # ancho útil
    
    # --------------- ENCABEZADO MARRÓN ---------------
    co_name = (company_info or {}).get('name', 'Empresa')
    co_addr = (company_info or {}).get('address', '')
    co_phone = (company_info or {}).get('phone', '')
    co_email = (company_info or {}).get('email', '')
    
    hdr_style = ParagraphStyle('H', parent=styles['Normal'], fontSize=8,
                               textColor=WHITE, alignment=TA_RIGHT, leading=12)
    
    logo = _get_logo(company_info)
    
    company_text = f"<b><font size='13'>{co_name}</font></b>"
    if co_addr:
        company_text += f"<br/>{co_addr}"
    if co_phone:
        company_text += f"<br/>Tel: {co_phone}"
    if co_email:
        company_text += f"<br/>{co_email}"
    
    if logo:
        hdr_data = [[logo, Paragraph(company_text, hdr_style)]]
        hdr_table = Table(hdr_data, colWidths=[1.2*inch, W - 1.2*inch])
    else:
        hdr_data = [[Paragraph(company_text, hdr_style)]]
        hdr_table = Table(hdr_data, colWidths=[W])
    
    hdr_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BROWN),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 14),
        ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
        ('RIGHTPADDING', (0,0), (-1,-1), 16),
    ]))
    story.append(hdr_table)
    story.append(Spacer(1, 0.2*inch))
    
    # --------------- TÍTULO + DATOS ---------------
    title_s = ParagraphStyle('T', parent=styles['Normal'], fontSize=18,
                             fontName='Helvetica-Bold', textColor=BROWN, leading=22)
    sub_s = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=9,
                           textColor=TEXT_MID, leading=13)
    right_s = ParagraphStyle('R', parent=styles['Normal'], fontSize=9,
                             textColor=TEXT_MID, alignment=TA_RIGHT, leading=13)
    
    resident_name = invoice_data.get('resident_name', 'Cliente')
    apt_number = invoice_data.get('apartment_number', 'N/A')
    payment_id = payment_data.get('id', '')
    payment_date = _fecha(payment_data.get('payment_date'))
    
    left_col = Paragraph("RECIBO DE PAGO", title_s)
    right_col = Paragraph(
        f"<b>Recibo No.</b> {payment_id}<br/>"
        f"<b>Fecha:</b> {payment_date}", right_s)
    
    t1 = Table([[left_col, right_col]], colWidths=[W*0.55, W*0.45])
    t1.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t1)
    story.append(Spacer(1, 0.15*inch))
    
    # --------------- CLIENTE (barra beige) ---------------
    client_s = ParagraphStyle('C', parent=styles['Normal'], fontSize=10,
                              textColor=TEXT_DARK, leading=14)
    
    client_text = (
        f"<b>{resident_name}</b>  ·  Apartamento {apt_number}"
    )
    resident_email = invoice_data.get('resident_email', '')
    if resident_email:
        client_text += f"  ·  {resident_email}"
    
    client_data = [[Paragraph(client_text, client_s)]]
    client_table = Table(client_data, colWidths=[W])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BROWN_BG),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 14),
        ('RIGHTPADDING', (0,0), (-1,-1), 14),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 0.2*inch))
    
    # --------------- DETALLE DE PAGO ---------------
    payment_amount = float(payment_data.get('amount', 0))
    payment_method = (payment_data.get('method', 'efectivo') or 'efectivo').capitalize()
    invoice_desc = invoice_data.get('description', 'Pago de factura')
    invoice_num = invoice_data.get('id', '')
    
    h_s = ParagraphStyle('TH', parent=styles['Normal'], fontSize=9,
                         fontName='Helvetica-Bold', textColor=WHITE)
    c_s = ParagraphStyle('TD', parent=styles['Normal'], fontSize=9,
                         textColor=TEXT_DARK, leading=13)
    r_s = ParagraphStyle('TDR', parent=styles['Normal'], fontSize=9,
                         textColor=TEXT_DARK, alignment=TA_RIGHT)
    
    detail = [
        [Paragraph('Factura', h_s), Paragraph('Concepto', h_s),
         Paragraph('Método', h_s), Paragraph('Monto', h_s)],
        [Paragraph(f'#{invoice_num}', c_s), Paragraph(invoice_desc, c_s),
         Paragraph(payment_method, c_s), Paragraph(_fmt(payment_amount), r_s)]
    ]
    
    dt = Table(detail, colWidths=[0.8*inch, W - 0.8*inch - 1.1*inch - 1.4*inch, 1.1*inch, 1.4*inch])
    dt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BROWN),
        ('TEXTCOLOR', (0,0), (-1,0), WHITE),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (3,0), (3,-1), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('LINEBELOW', (0,1), (-1,1), 0.5, BROWN_LIGHT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(dt)
    story.append(Spacer(1, 0.15*inch))
    
    # --------------- NOTAS ---------------
    payment_notes = (payment_data.get('notes', '') or '').strip()
    if payment_notes:
        note_s = ParagraphStyle('N', parent=styles['Normal'], fontSize=8,
                                textColor=TEXT_MID, leading=12)
        note_data = [[Paragraph(f"<b>Nota:</b> {payment_notes}", note_s)]]
        nt = Table(note_data, colWidths=[W])
        nt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BROWN_BG),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ]))
        story.append(nt)
        story.append(Spacer(1, 0.15*inch))
    
    # --------------- RESUMEN FINANCIERO ---------------
    invoice_amount = float(invoice_data.get('amount', 0))
    total_paid = float(invoice_data.get('total_paid', payment_amount))
    remaining = invoice_amount - total_paid
    
    bal_color = GREEN_OK if remaining <= 0 else RED_DANGER
    bal_text = 'PAGADO' if remaining <= 0 else _fmt(remaining)
    
    lbl = ParagraphStyle('LBL', parent=styles['Normal'], fontSize=10,
                         fontName='Helvetica-Bold', textColor=TEXT_DARK, alignment=TA_RIGHT)
    val = ParagraphStyle('VAL', parent=styles['Normal'], fontSize=10,
                         textColor=TEXT_DARK, alignment=TA_RIGHT)
    
    summary = [
        [Paragraph('Total Factura:', lbl), Paragraph(_fmt(invoice_amount), val)],
        [Paragraph('Pagado:', lbl), Paragraph(_fmt(total_paid), val)],
    ]
    
    st = Table(summary, colWidths=[W - 1.8*inch, 1.8*inch])
    st.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(st)
    
    # Balance row (destacado)
    bal_lbl = ParagraphStyle('BLBL', parent=styles['Normal'], fontSize=13,
                             fontName='Helvetica-Bold', textColor=BROWN, alignment=TA_RIGHT)
    bal_val = ParagraphStyle('BVAL', parent=styles['Normal'], fontSize=13,
                             fontName='Helvetica-Bold', textColor=bal_color, alignment=TA_RIGHT)
    
    bal_data = [[Paragraph('Saldo Pendiente:', bal_lbl), Paragraph(bal_text, bal_val)]]
    bt = Table(bal_data, colWidths=[W - 1.8*inch, 1.8*inch])
    bt.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,0), 2, BROWN),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(bt)
    story.append(Spacer(1, 0.4*inch))
    
    # --------------- FOOTER ---------------
    ft_s = ParagraphStyle('FT', parent=styles['Normal'], fontSize=7,
                          textColor=TEXT_LIGHT, alignment=TA_CENTER, leading=10)
    story.append(Paragraph(
        f"<i>Gracias por su pago puntual.  ·  Documento generado el {_fecha()}</i>", ft_s))
    
    # Build
    doc.build(story)
    if output_path:
        return None
    buffer.seek(0)
    return buffer


# ============================================================
#  ESTADO DE CUENTA
# ============================================================
def generate_account_statement_pdf(unit_data, invoices, payments, company_info, output_path=None):
    """Genera un estado de cuenta compacto con esquema marrón/blanco"""
    
    if output_path:
        doc = SimpleDocTemplate(output_path, pagesize=letter,
                                rightMargin=0.6*inch, leftMargin=0.6*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
    else:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=0.6*inch, leftMargin=0.6*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    story = []
    styles = getSampleStyleSheet()
    W = 6.8 * inch
    
    # --------------- ENCABEZADO MARRÓN ---------------
    co_name = (company_info or {}).get('name', 'Empresa')
    co_addr = (company_info or {}).get('address', '')
    co_phone = (company_info or {}).get('phone', '')
    co_email = (company_info or {}).get('email', '')
    
    hdr_s = ParagraphStyle('H', parent=styles['Normal'], fontSize=8,
                           textColor=WHITE, alignment=TA_RIGHT, leading=12)
    
    logo = _get_logo(company_info)
    
    co_text = f"<b><font size='13'>{co_name}</font></b>"
    if co_addr:
        co_text += f"<br/>{co_addr}"
    if co_phone:
        co_text += f"<br/>Tel: {co_phone}"
    if co_email:
        co_text += f"<br/>{co_email}"
    
    if logo:
        hdr_data = [[logo, Paragraph(co_text, hdr_s)]]
        hdr_table = Table(hdr_data, colWidths=[1.2*inch, W - 1.2*inch])
    else:
        hdr_data = [[Paragraph(co_text, hdr_s)]]
        hdr_table = Table(hdr_data, colWidths=[W])
    
    hdr_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BROWN),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 14),
        ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
        ('RIGHTPADDING', (0,0), (-1,-1), 16),
    ]))
    story.append(hdr_table)
    story.append(Spacer(1, 0.2*inch))
    
    # --------------- TÍTULO + CLIENTE ---------------
    title_s = ParagraphStyle('T', parent=styles['Normal'], fontSize=18,
                             fontName='Helvetica-Bold', textColor=BROWN, leading=22)
    right_s = ParagraphStyle('R', parent=styles['Normal'], fontSize=9,
                             textColor=TEXT_MID, alignment=TA_RIGHT, leading=13)
    
    resident_name = unit_data.get('resident_name', 'N/A')
    unit_number = unit_data.get('number', 'N/A')
    
    left_col = Paragraph("ESTADO DE CUENTA", title_s)
    right_col = Paragraph(
        f"<b>{resident_name}</b><br/>"
        f"Apartamento {unit_number}<br/>"
        f"{_fecha()}", right_s)
    
    t1 = Table([[left_col, right_col]], colWidths=[W*0.55, W*0.45])
    t1.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(t1)
    story.append(Spacer(1, 0.2*inch))
    
    # --------------- FACTURAS ---------------
    sec_s = ParagraphStyle('SEC', parent=styles['Normal'], fontSize=11,
                           fontName='Helvetica-Bold', textColor=BROWN, spaceAfter=6)
    
    story.append(Paragraph("FACTURAS", sec_s))
    
    th_s = ParagraphStyle('TH', parent=styles['Normal'], fontSize=8,
                          fontName='Helvetica-Bold', textColor=WHITE)
    td_s = ParagraphStyle('TD', parent=styles['Normal'], fontSize=8,
                          textColor=TEXT_DARK)
    td_r = ParagraphStyle('TDR', parent=styles['Normal'], fontSize=8,
                          textColor=TEXT_DARK, alignment=TA_RIGHT)
    td_c = ParagraphStyle('TDC', parent=styles['Normal'], fontSize=8,
                          textColor=TEXT_DARK, alignment=TA_CENTER)
    
    inv_rows = [
        [Paragraph('#', th_s), Paragraph('Fecha', th_s),
         Paragraph('Descripción', th_s), Paragraph('Monto', th_s),
         Paragraph('Estado', th_s)]
    ]
    total_invoiced = 0
    
    for inv in invoices:
        inv_id = str(inv.get('id', ''))
        issued = str(inv.get('issued_date', ''))[:10]
        desc = inv.get('description', '')
        if len(desc) > 40:
            desc = desc[:37] + '...'
        amount = float(inv.get('amount', 0))
        status = 'Pagada' if inv.get('paid') else 'Pendiente'
        total_invoiced += amount
        
        s_color = GREEN_OK if inv.get('paid') else RED_DANGER
        status_s = ParagraphStyle('ST', parent=styles['Normal'], fontSize=8,
                                  fontName='Helvetica-Bold', textColor=s_color, alignment=TA_CENTER)
        
        inv_rows.append([
            Paragraph(inv_id, td_c), Paragraph(issued, td_c),
            Paragraph(desc, td_s), Paragraph(_fmt(amount), td_r),
            Paragraph(status, status_s)
        ])
    
    inv_t = Table(inv_rows, colWidths=[0.4*inch, 0.85*inch, W - 0.4*inch - 0.85*inch - 1.2*inch - 0.85*inch, 1.2*inch, 0.85*inch])
    inv_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BROWN),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('LINEBELOW', (0,0), (-1,0), 0, WHITE),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, BROWN_BG]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(inv_t)
    story.append(Spacer(1, 0.2*inch))
    
    # --------------- PAGOS ---------------
    if payments:
        story.append(Paragraph("PAGOS RECIBIDOS", sec_s))
        
        pay_rows = [
            [Paragraph('#', th_s), Paragraph('Fecha', th_s),
             Paragraph('Factura', th_s), Paragraph('Método', th_s),
             Paragraph('Monto', th_s)]
        ]
        total_paid = 0
        
        for pay in payments:
            p_id = str(pay.get('id', ''))
            p_date = str(pay.get('paid_date', ''))[:10]
            p_inv = str(pay.get('invoice_id', ''))
            p_method = (pay.get('method', '') or '').capitalize()
            p_amount = float(pay.get('amount', 0))
            total_paid += p_amount
            
            pay_rows.append([
                Paragraph(p_id, td_c), Paragraph(p_date, td_c),
                Paragraph(f'#{p_inv}', td_c), Paragraph(p_method, td_s),
                Paragraph(_fmt(p_amount), td_r)
            ])
        
        pay_t = Table(pay_rows, colWidths=[0.4*inch, 0.85*inch, 0.7*inch, W - 0.4*inch - 0.85*inch - 0.7*inch - 1.2*inch, 1.2*inch])
        pay_t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), BROWN_DARK),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, BROWN_BG]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(pay_t)
        story.append(Spacer(1, 0.2*inch))
    else:
        total_paid = 0
    
    # --------------- BALANCE ---------------
    balance = total_invoiced - total_paid
    bal_color = RED_DANGER if balance > 0 else GREEN_OK
    
    lbl = ParagraphStyle('LBL', parent=styles['Normal'], fontSize=10,
                         fontName='Helvetica-Bold', textColor=TEXT_DARK, alignment=TA_RIGHT)
    val = ParagraphStyle('VAL', parent=styles['Normal'], fontSize=10,
                         textColor=TEXT_DARK, alignment=TA_RIGHT)
    
    s_rows = [
        [Paragraph('Total Facturado:', lbl), Paragraph(_fmt(total_invoiced), val)],
        [Paragraph('Total Pagado:', lbl), Paragraph(_fmt(total_paid), val)],
    ]
    st = Table(s_rows, colWidths=[W - 1.8*inch, 1.8*inch])
    st.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(st)
    
    bal_lbl = ParagraphStyle('BLBL', parent=styles['Normal'], fontSize=14,
                             fontName='Helvetica-Bold', textColor=BROWN, alignment=TA_RIGHT)
    bal_val = ParagraphStyle('BVAL', parent=styles['Normal'], fontSize=14,
                             fontName='Helvetica-Bold', textColor=bal_color, alignment=TA_RIGHT)
    
    bt = Table(
        [[Paragraph('Balance Pendiente:', bal_lbl), Paragraph(_fmt(balance), bal_val)]],
        colWidths=[W - 1.8*inch, 1.8*inch]
    )
    bt.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,0), 2, BROWN),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(bt)
    story.append(Spacer(1, 0.4*inch))
    
    # --------------- FOOTER ---------------
    ft_s = ParagraphStyle('FT', parent=styles['Normal'], fontSize=7,
                          textColor=TEXT_LIGHT, alignment=TA_CENTER, leading=10)
    story.append(Paragraph(
        f"<i>Documento generado el {_fecha()}  ·  Este documento no requiere firma</i>", ft_s))
    
    # Build
    doc.build(story)
    if output_path:
        return None
    buffer.seek(0)
    return buffer
