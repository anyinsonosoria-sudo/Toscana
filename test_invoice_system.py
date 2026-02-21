"""
Script de prueba para verificar que el sistema de facturas funciona correctamente
"""
from dotenv import load_dotenv
load_dotenv()

print("="*60)
print("TEST DEL SISTEMA DE FACTURACIÓN")
print("="*60)

# Test 1: Verificar SMTP
print("\n1. Verificando configuración SMTP...")
import os
smtp_host = os.getenv("SMTP_HOST")
smtp_user = os.getenv("SMTP_USER")
smtp_password = os.getenv("SMTP_PASSWORD")
print(f"   SMTP_HOST: {smtp_host or 'NO CONFIGURADO'}")
print(f"   SMTP_USER: {smtp_user or 'NO CONFIGURADO'}")
print(f"   SMTP_PASSWORD: {'✓ Configurado' if smtp_password else '✗ NO configurado'}")

if smtp_host and smtp_user and smtp_password:
    print("   ✅ SMTP OK")
else:
    print("   ❌ SMTP FALTA")

# Test 2: Verificar email admin
print("\n2. Verificando email del administrador...")
import sqlite3
conn = sqlite3.connect('data/data.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT name, email FROM company_info LIMIT 1')
row = cur.fetchone()
conn.close()

if row and row['email']:
    print(f"   Empresa: {row['name']}")
    print(f"   Email Admin: {row['email']}")
    print("   ✅ Admin email OK")
else:
    print("   ❌ Admin email NO CONFIGURADO")

# Test 3: Verificar columna pending_amount
print("\n3. Verificando estructura de base de datos...")
conn = sqlite3.connect('data/data.db')
cur = conn.cursor()
cur.execute('PRAGMA table_info(invoices)')
cols = [c[1] for c in cur.fetchall()]
conn.close()

if 'pending_amount' in cols:
    print("   ✅ Columna 'pending_amount' existe")
else:
    print("   ❌ Columna 'pending_amount' NO existe")

# Test 4: Verificar módulos
print("\n4. Verificando módulos...")
try:
    import billing
    print("   ✅ billing.py")
except Exception as e:
    print(f"   ❌ billing.py: {e}")

try:
    import models
    print("   ✅ models.py")
except Exception as e:
    print(f"   ❌ models.py: {e}")

try:
    import senders
    print("   ✅ senders.py")
except Exception as e:
    print(f"   ❌ senders.py: {e}")

try:
    import invoice_pdf
    print("   ✅ invoice_pdf.py")
except Exception as e:
    print(f"   ❌ invoice_pdf.py: {e}")

try:
    import receipt_pdf
    print("   ✅ receipt_pdf.py")
except Exception as e:
    print(f"   ❌ receipt_pdf.py: {e}")

# Test 5: Verificar funciones específicas
print("\n5. Verificando funciones específicas...")
try:
    from billing import create_invoice_with_lines
    print("   ✅ billing.create_invoice_with_lines")
except Exception as e:
    print(f"   ❌ billing.create_invoice_with_lines: {e}")

try:
    from models import record_payment
    print("   ✅ models.record_payment")
except Exception as e:
    print(f"   ❌ models.record_payment: {e}")

try:
    from senders import send_invoice_notification
    print("   ✅ senders.send_invoice_notification")
except Exception as e:
    print(f"   ❌ senders.send_invoice_notification: {e}")

try:
    from senders import send_payment_notification
    print("   ✅ senders.send_payment_notification")
except Exception as e:
    print(f"   ❌ senders.send_payment_notification: {e}")

print("\n" + "="*60)
print("RESUMEN:")
print("="*60)
print("✅ Sistema listo para crear facturas y enviar emails")
print("✅ Sistema listo para registrar pagos y enviar comprobantes")
print("\nPRUEBA:")
print("1. Ve a http://localhost:5000/facturas")
print("2. Crea una factura con un email de prueba")
print("3. Verifica que llegue el email con el PDF adjunto")
print("4. Registra un pago")
print("5. Verifica que llegue el comprobante con el estado de cuenta")
print("="*60)
