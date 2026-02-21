"""
Módulo para generar facturas en PDF con diseño simple y profesional
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime
from pathlib import Path
import os

def format_currency(amount):
    """Formatea un número como moneda: RD$ 1,000.00"""
    if amount is None:
        amount = 0
    return f"RD$ {amount:,.2f}"

def get_company_info():
    """Obtiene información de la empresa"""
    try:
        from company import get_company_info as get_info
        return get_info()
    except:
        return {}

def get_accent_color():
    """Obtiene el color de acento"""
    try:
        from customization import get_setting
        return get_setting('accent_color', '#795547')
    except:
        return '#795547'

def generate_invoice(invoice_data, output_path):
    """
    Genera una factura en PDF con diseño simple y profesional.
    
    Estructura:
    - Encabezado: Color con logo e información de empresa
    - Sección media: Tabla con código, descripción, precio, cantidad, monto
    - Totales: Total y Monto a pagar
    - Footer: Descripción adicional y notas
    
    Args:
        invoice_data: Diccionario con los datos de la factura
        output_path: Ruta donde se guardará el PDF
    """
    # Obtener información de la empresa
    company_info = get_company_info()
    accent_color_hex = get_accent_color()
    
    # Convertir color hexadecimal a RGB
    try:
        hex_color = accent_color_hex.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        accent_color = colors.Color(r/255.0, g/255.0, b/255.0)
    except:
        accent_color = colors.HexColor('#795547')
    
    # Crear el PDF
    doc = SimpleDocTemplate(output_path, pagesize=letter, 
                           topMargin=0.5*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    
    story = []
    styles = getSampleStyleSheet()
    
    # ===== ENCABEZADO CON COLOR (LOGO E INFORMACIÓN DE EMPRESA) =====
    header_elements = []
    
    # Logo (si existe) - Mejorar la ruta de búsqueda
    logo_element = None
    if company_info and company_info.get('logo_path'):
        logo_filename = company_info['logo_path']
        
        # Intentar múltiples rutas posibles
        possible_paths = [
            os.path.join('static', 'uploads', logo_filename),
            os.path.join(os.path.dirname(__file__), 'static', 'uploads', logo_filename),
            logo_filename if os.path.isabs(logo_filename) else None
        ]
        
        for path in possible_paths:
            if path and os.path.exists(path):
                try:
                    # Logo más grande y con mejor proporción
                    logo_element = Image(path, width=1.8*inch, height=1.2*inch, kind='proportional')
                    break
                except Exception as e:
                    print(f"Error cargando logo desde {path}: {e}")
                    continue
    
    if logo_element:
        header_elements.append(logo_element)
    else:
        # Espacio vacío si no hay logo
        header_elements.append(Paragraph("", styles['Normal']))
    
    # Información de la empresa
    company_name = company_info.get('name', 'Nombre de Empresa') if company_info else 'Nombre de Empresa'
    company_address = company_info.get('address', '') if company_info else ''
    company_city = company_info.get('city', '') if company_info else ''
    company_country = company_info.get('country', '') if company_info else ''
    company_phone = company_info.get('phone', '') if company_info else ''
    company_email = company_info.get('email', '') if company_info else ''
    
    # Construir información de empresa con mejor formato
    company_info_lines = [f"<b><font size='14'>{company_name}</font></b>"]
    if company_address:
        company_info_lines.append(f"<font size='10'>{company_address}</font>")
    
    location = f"{company_city}, {company_country}".strip(', ')
    if location:
        company_info_lines.append(f"<font size='10'>{location}</font>")
    
    if company_phone:
        phones = [p.strip() for p in company_phone.split(',')]
        for phone in phones:
            if phone:
                company_info_lines.append(f"<font size='9'>Tel: {phone}</font>")
    
    if company_email:
        company_info_lines.append(f"<font size='9'>{company_email}</font>")
    
    company_info_text = '<br/>'.join(company_info_lines)
    company_para = Paragraph(company_info_text, 
                            ParagraphStyle('CompanyHeader', 
                                         parent=styles['Normal'],
                                         fontSize=10,
                                         textColor=colors.white,
                                         alignment=TA_RIGHT,
                                         leading=16,
                                         spaceAfter=0))
    header_elements.append(company_para)
    
    # Tabla del encabezado con fondo de color
    header_table = Table([header_elements], colWidths=[2.2*inch, 4.8*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), accent_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 20),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 0.35*inch))
    
    # ===== SECCIÓN A: INFORMACIÓN DEL CLIENTE (IZQUIERDA) Y DATOS DE FACTURA (DERECHA) =====
    amount = float(invoice_data.get('amount', 0))
    description = invoice_data.get('description', 'Servicio')
    notes = invoice_data.get('notes', '')
    service_code = invoice_data.get('service_code', 'N/A')
    
    # Formatear fechas
    try:
        issued_dt = datetime.strptime(invoice_data.get('issued_date', ''), '%Y-%m-%d')
        # Traducir mes a español y formatear como "14 de Marzo de 2026"
        months_es = {
            'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
            'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
            'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
            'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
        }
        issued_date_eng = issued_dt.strftime('%d de %B de %Y')
        issued_date = issued_date_eng
        for eng, esp in months_es.items():
            issued_date = issued_date.replace(eng, esp)
    except:
        issued_date = invoice_data.get('issued_date', '')
    
    try:
        due_dt = datetime.strptime(invoice_data.get('due_date', ''), '%Y-%m-%d')
        due_date_eng = due_dt.strftime('%d de %B de %Y')
        due_date = due_date_eng
        for eng, esp in months_es.items():
            due_date = due_date.replace(eng, esp)
    except:
        due_date = invoice_data.get('due_date', '')
    
    # Información básica
    resident_name = invoice_data.get('resident_name', 'Cliente')
    apartment_num = invoice_data.get('apartment_number', '')
    resident_phone = invoice_data.get('resident_phone', '')
    resident_email = invoice_data.get('resident_email', '')
    invoice_num = invoice_data.get('id', '')
    
    # Estilos
    label_style = ParagraphStyle('Label', parent=styles['Normal'], 
                                 fontSize=10, fontName='Helvetica-Bold',
                                 spaceAfter=4, leading=14)
    
    data_style = ParagraphStyle('Data', parent=styles['Normal'], 
                                fontSize=10, leading=14, spaceAfter=4)
    
    # COLUMNA IZQUIERDA: Información del cliente
    client_info = f"""
    <b>CLIENTE</b><br/>
    {resident_name}<br/>
    Apartamento: {apartment_num}<br/>
    Tel: {resident_phone}<br/>
    Email: {resident_email}
    """
    
    client_para = Paragraph(client_info, data_style)
    
    # Estilo para la columna derecha (alineado a derecha)
    right_align_style = ParagraphStyle('RightAlign', parent=styles['Normal'], 
                                      fontSize=10, leading=14, spaceAfter=4,
                                      alignment=TA_RIGHT)
    
    # COLUMNA DERECHA: Datos de la factura (todo en negrita)
    invoice_info = f"""
    <b>Número de Factura:</b> {invoice_num}<br/>
    <b>Fecha de Emisión:</b> {issued_date}<br/>
    <b>Fecha de Vencimiento:</b> {due_date}<br/>
    <br/>
    <b>Monto a Pagar:</b> {format_currency(amount)}
    """
    
    invoice_para = Paragraph(invoice_info, right_align_style)
    
    # Tabla con dos columnas
    section_a_data = [[client_para, invoice_para]]
    section_a_table = Table(section_a_data, colWidths=[3.5*inch, 3.5*inch])
    section_a_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    
    story.append(section_a_table)
    story.append(Spacer(1, 0.35*inch))
    
    # ===== SECCIÓN MEDIA: TABLA DE SERVICIOS CON BORDES ESTILO EXCEL =====
    # Título de sección
    section_title = Paragraph("<b>DETALLE DEL SERVICIO</b>", 
                             ParagraphStyle('SectionTitle', parent=styles['Normal'],
                                          fontSize=11, fontName='Helvetica-Bold',
                                          textColor=accent_color, spaceAfter=8))
    story.append(section_title)
    
    table_header_style = ParagraphStyle('TableHeader', parent=styles['Normal'], 
                                       fontSize=10, fontName='Helvetica-Bold',
                                       textColor=colors.white, alignment=TA_CENTER)
    
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'],
                               fontSize=10, alignment=TA_CENTER)
    
    desc_style = ParagraphStyle('DescStyle', parent=styles['Normal'],
                                fontSize=10, alignment=TA_LEFT)
    
    table_data = [
        [
            Paragraph('Código', table_header_style),
            Paragraph('Descripción', table_header_style),
            Paragraph('Precio', table_header_style),
            Paragraph('Cantidad', table_header_style),
            Paragraph('Monto', table_header_style)
        ],
        [
            Paragraph(service_code, cell_style),
            Paragraph(description, desc_style),
            Paragraph(format_currency(amount), cell_style),
            Paragraph('1', cell_style),
            Paragraph(format_currency(amount), cell_style)
        ]
    ]
    
    service_table = Table(table_data, colWidths=[0.9*inch, 2.8*inch, 1.2*inch, 0.9*inch, 1.2*inch])
    service_table.setStyle(TableStyle([
        # Encabezado con color
        ('BACKGROUND', (0, 0), (-1, 0), accent_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (-1, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        # Contenido
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (0, 1), (0, 1), 'CENTER'),
        ('ALIGN', (1, 1), (1, 1), 'LEFT'),
        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        # Bordes estilo Excel - todas las celdas separadas
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(service_table)
    story.append(Spacer(1, 0.25*inch))
    
    # ===== TOTALES =====
    totals_data = [
        ['Total:', format_currency(amount)],
        ['', ''],
        ['Monto a Pagar:', format_currency(amount)]
    ]
    
    totals_table = Table(totals_data, colWidths=[5.5*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        # Total
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, 0), 'Helvetica'),
        ('FONTSIZE', (0, 0), (1, 0), 11),
        ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        # Monto a Pagar (destacado)
        ('FONTNAME', (0, 2), (1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 2), (1, 2), 13),
        ('TEXTCOLOR', (0, 2), (1, 2), accent_color),
        ('ALIGN', (0, 2), (0, 2), 'RIGHT'),
        ('ALIGN', (1, 2), (1, 2), 'RIGHT'),
        ('LINEABOVE', (0, 2), (1, 2), 2, accent_color),
        ('TOPPADDING', (0, 2), (1, 2), 8),
        ('BOTTOMPADDING', (0, 2), (1, 2), 8),
    ]))
    
    story.append(totals_table)
    story.append(Spacer(1, 0.5*inch))
    
    # ===== FOOTER: DESCRIPCIÓN ADICIONAL Y NOTAS =====
    footer_title_style = ParagraphStyle('FooterTitle', parent=styles['Normal'], 
                                       fontSize=10, fontName='Helvetica-Bold',
                                       textColor=accent_color, spaceAfter=8)
    
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], 
                                 fontSize=9, leading=14, spaceAfter=6)
    
    # Descripción adicional - aquí va el texto largo del servicio
    story.append(Paragraph("DESCRIPCIÓN ADICIONAL", footer_title_style))
    
    # Si hay notas (additional_notes), usarlas; si no, no mostrar nada o usar un valor por defecto
    if notes:
        story.append(Paragraph(notes, footer_style))
    else:
        # Si no hay additional_notes, no mostrar la sección o mostrar texto genérico
        story.append(Paragraph("Servicio mensual", footer_style))
    
    story.append(Spacer(1, 0.25*inch))
    
    # Notas generales
    story.append(Paragraph("NOTAS", footer_title_style))
    
    notes_list = [
        "Cargo mensual para pago de energía eléctrica, mantenimiento, reparaciones menores y conserjería del área común.",
        "<br/>",
        "Para transferencia bancaria usar cuenta de Ahorro Banreservas 9601250790. Para pagos en efectivo favor contactar a Williams Osoria (1A) o Eduardo Rodríguez (2B)."
    ]
    
    for note in notes_list:
        story.append(Paragraph(note, footer_style))
        story.append(Spacer(1, 0.05*inch))
    
    # Construir el PDF
    doc.build(story)

# Compatibilidad con código anterior
def generate_invoice_pdf(invoice_data, company_info, output_path=None):
    """Función de compatibilidad - redirige a generate_invoice"""
    if output_path:
        generate_invoice(invoice_data, output_path)
    else:
        # Si no hay output_path, usar un buffer
        import io
        buffer = io.BytesIO()
        generate_invoice(invoice_data, buffer)
        buffer.seek(0)
        return buffer
