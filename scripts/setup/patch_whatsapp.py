"""Patch para agregar soporte de WhatsApp en estado de cuenta"""

# Leer el archivo
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Buscar y reemplazar (usando solo el patrón sin el print problemático)
target_line = "                            client_phone=resident.get('phone')\n                        )"

if target_line in content:
    # Encontrar la posición
    pos = content.find(target_line)
    # Encontrar el final de la línea siguiente (después del cierre del paréntesis)
    next_newline = content.find('\n', pos + len(target_line))
    
    # Insertar código después de la línea
    insert_code = """
                        
                        # Enviar estado de cuenta por WhatsApp también
                        if resident.get('phone'):
                            try:
                                total_invoiced = sum(inv.get('amount', 0) for inv in unit_invoices)
                                total_paid = sum(pay.get('amount', 0) for pay in unit_payments)
                                balance = total_invoiced - total_paid
                                unit_data['resident_name'] = resident.get('name', 'N/A')
                                senders.send_statement_whatsapp(unit_data, unit_invoices, unit_payments, balance, resident.get('phone'))
                            except Exception as whatsapp_err:
                                print(f"Error sending statement via WhatsApp: {whatsapp_err}")"""
    
    content = content[:next_newline] + insert_code + content[next_newline:]
    
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✓ Patch aplicado exitosamente")
else:
    print("✗ No se encontró el código objetivo")
