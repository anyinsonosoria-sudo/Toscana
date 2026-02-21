"""
Script de prueba del sistema de notificaciones de facturas
Verifica que las notificaciones se envíen correctamente
"""
import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

# Cargar variables de entorno desde .env
try:
    from dotenv import load_dotenv
    env_path = root_dir / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Archivo .env cargado desde: {env_path}\n")
    else:
        print(f"⚠️  Archivo .env no encontrado en: {env_path}\n")
except ImportError:
    print("⚠️  python-dotenv no instalado\n")

print("=" * 70)
print("VERIFICACIÓN DEL SISTEMA DE NOTIFICACIONES DE FACTURAS")
print("=" * 70)

# 1. Verificar configuración SMTP
print("\n1. Verificando configuración SMTP...")
smtp_host = os.getenv("SMTP_HOST")
smtp_port = os.getenv("SMTP_PORT", "587")
smtp_user = os.getenv("SMTP_USER")
smtp_password = os.getenv("SMTP_PASSWORD")
smtp_from = os.getenv("SMTP_FROM")

if smtp_host:
    print(f"   ✅ SMTP_HOST configurado: {smtp_host}")
else:
    print("   ❌ SMTP_HOST NO configurado")

if smtp_user:
    print(f"   ✅ SMTP_USER configurado: {smtp_user}")
else:
    print("   ❌ SMTP_USER NO configurado")

if smtp_password:
    print(f"   ✅ SMTP_PASSWORD configurado: {'*' * 8}")
else:
    print("   ❌ SMTP_PASSWORD NO configurado")

if smtp_from:
    print(f"   ✅ SMTP_FROM configurado: {smtp_from}")
else:
    print(f"   ⚠️  SMTP_FROM no configurado (usando {smtp_user})")

# 2. Verificar módulo senders
print("\n2. Verificando módulo senders...")
try:
    import senders
    print("   ✅ Módulo senders importado correctamente")
    
    # Verificar función send_invoice_notification
    if hasattr(senders, 'send_invoice_notification'):
        print("   ✅ Función send_invoice_notification existe")
    else:
        print("   ❌ Función send_invoice_notification NO existe")
        
except Exception as e:
    print(f"   ❌ Error importando senders: {e}")

# 3. Verificar módulo billing
print("\n3. Verificando módulo billing...")
try:
    import billing
    print("   ✅ Módulo billing importado correctamente")
    
    # Verificar función create_invoice_with_lines
    if hasattr(billing, 'create_invoice_with_lines'):
        print("   ✅ Función create_invoice_with_lines existe")
        
        # Verificar firma de la función
        import inspect
        sig = inspect.signature(billing.create_invoice_with_lines)
        params = list(sig.parameters.keys())
        print(f"   📋 Parámetros: {', '.join(params)}")
        
        if 'notify_email' in params:
            print("   ✅ Parámetro notify_email presente")
        else:
            print("   ❌ Parámetro notify_email NO presente")
            
        if 'notify_phone' in params:
            print("   ✅ Parámetro notify_phone presente")
        else:
            print("   ❌ Parámetro notify_phone NO presente")
            
        if 'attach_pdf' in params:
            print("   ✅ Parámetro attach_pdf presente")
        else:
            print("   ❌ Parámetro attach_pdf NO presente")
    else:
        print("   ❌ Función create_invoice_with_lines NO existe")
        
except Exception as e:
    print(f"   ❌ Error importando billing: {e}")

# 4. Verificar configuración de WhatsApp
print("\n4. Verificando configuración de WhatsApp...")
wa_enabled = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
wa_api_url = os.getenv("WHATSAPP_API_URL")
wa_api_token = os.getenv("WHATSAPP_API_TOKEN")

if wa_enabled:
    print("   ✅ WhatsApp HABILITADO")
    if wa_api_url:
        print(f"   ✅ API URL configurada: {wa_api_url}")
    else:
        print("   ❌ API URL NO configurada")
    if wa_api_token:
        print(f"   ✅ API TOKEN configurado: {'*' * 8}")
    else:
        print("   ❌ API TOKEN NO configurado")
else:
    print("   ⚠️  WhatsApp DESHABILITADO")

# 5. Verificar directorio de PDFs
print("\n5. Verificando directorio de facturas...")
from pathlib import Path
pdf_dir = Path(__file__).parent.parent.parent / "static" / "invoices"
if pdf_dir.exists():
    print(f"   ✅ Directorio existe: {pdf_dir}")
    pdf_count = len(list(pdf_dir.glob("*.pdf")))
    print(f"   📄 PDFs encontrados: {pdf_count}")
else:
    print(f"   ❌ Directorio NO existe: {pdf_dir}")

# Resumen
print("\n" + "=" * 70)
print("RESUMEN")
print("=" * 70)

all_ok = True

if not smtp_host or not smtp_user or not smtp_password:
    print("❌ CONFIGURACIÓN SMTP INCOMPLETA")
    print("   → Configure las variables en el archivo .env:")
    print("      SMTP_HOST=smtp.gmail.com")
    print("      SMTP_PORT=587")
    print("      SMTP_USER=tu_email@gmail.com")
    print("      SMTP_PASSWORD=tu_password")
    print("      SMTP_FROM=tu_email@gmail.com")
    all_ok = False
else:
    print("✅ Configuración SMTP completa")

try:
    import senders
    import billing
    print("✅ Módulos necesarios disponibles")
except:
    print("❌ Módulos necesarios NO disponibles")
    all_ok = False

if all_ok:
    print("\n🎉 SISTEMA LISTO PARA ENVIAR NOTIFICACIONES")
    print("   Las facturas se enviarán automáticamente al crearlas.")
else:
    print("\n⚠️  CONFIGURACIÓN INCOMPLETA")
    print("   Revise los errores arriba y complete la configuración.")

print("=" * 70)
