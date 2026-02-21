"""Test de configuración SMTP y email del administrador"""
from dotenv import load_dotenv
load_dotenv()

import os
import sqlite3

print("=" * 50)
print("DIAGNÓSTICO DE CONFIGURACIÓN DE EMAIL")
print("=" * 50)

# Verificar SMTP
print("\n1. CONFIGURACIÓN SMTP (desde .env):")
smtp_host = os.getenv("SMTP_HOST")
smtp_user = os.getenv("SMTP_USER")
smtp_password = os.getenv("SMTP_PASSWORD")
smtp_from = os.getenv("SMTP_FROM")

print(f"   SMTP_HOST: {smtp_host or 'NO CONFIGURADO'}")
print(f"   SMTP_USER: {smtp_user or 'NO CONFIGURADO'}")
print(f"   SMTP_FROM: {smtp_from or 'NO CONFIGURADO'}")
print(f"   SMTP_PASSWORD: {'[CONFIGURADO]' if smtp_password else 'NO CONFIGURADO'}")

smtp_ok = all([smtp_host, smtp_user, smtp_password])
print(f"\n   ✅ SMTP OK" if smtp_ok else "\n   ❌ SMTP INCOMPLETO")

# Verificar email admin
print("\n2. EMAIL DEL ADMINISTRADOR (desde base de datos):")
try:
    conn = sqlite3.connect('data/data.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT name, email FROM company_info LIMIT 1')
    row = cur.fetchone()
    conn.close()
    
    if row:
        admin_email = row['email']
        print(f"   Empresa: {row['name'] or 'Sin nombre'}")
        print(f"   Email Admin: {admin_email or 'NO CONFIGURADO'}")
        admin_ok = bool(admin_email)
    else:
        print("   Empresa: NO CONFIGURADA")
        print("   Email Admin: NO CONFIGURADO")
        admin_ok = False
except Exception as e:
    print(f"   Error: {e}")
    admin_ok = False

print(f"\n   ✅ Admin Email OK" if admin_ok else "\n   ❌ Admin Email FALTA")

# Test de conexión SMTP
print("\n3. TEST DE CONEXIÓN SMTP:")
if smtp_ok:
    try:
        import smtplib
        server = smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "587")), timeout=10)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.quit()
        print("   ✅ Conexión SMTP exitosa!")
    except Exception as e:
        print(f"   ❌ Error de conexión: {e}")
else:
    print("   ⏭️ Saltando (SMTP no configurado)")

# Resumen
print("\n" + "=" * 50)
print("RESUMEN:")
if smtp_ok and admin_ok:
    print("✅ TODO LISTO - Los emails deberían funcionar")
elif smtp_ok and not admin_ok:
    print("⚠️ FALTA: Configurar email del administrador")
    print("   → Ve a: http://localhost:5000/settings/empresa")
    print("   → Ingresa el email del administrador")
elif not smtp_ok:
    print("❌ FALTA: Configurar SMTP en archivo .env")
print("=" * 50)
