"""
Script de prueba para verificar configuración de email SMTP
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def test_smtp_config():
    """Verifica que la configuración SMTP esté presente"""
    print("=" * 50)
    print("VERIFICACIÓN DE CONFIGURACIÓN SMTP")
    print("=" * 50)
    
    config = {
        'SMTP_HOST': os.getenv('SMTP_HOST'),
        'SMTP_PORT': os.getenv('SMTP_PORT'),
        'SMTP_USER': os.getenv('SMTP_USER'),
        'SMTP_PASSWORD': os.getenv('SMTP_PASSWORD'),
        'SMTP_FROM': os.getenv('SMTP_FROM')
    }
    
    print("\nConfiguración actual:")
    for key, value in config.items():
        if value:
            # Ocultar password
            if 'PASSWORD' in key:
                masked = value[:4] + '*' * (len(value) - 4) if len(value) > 4 else '****'
                print(f"  ✓ {key}: {masked}")
            else:
                print(f"  ✓ {key}: {value}")
        else:
            print(f"  ✗ {key}: NO CONFIGURADO")
    
    # Verificar si está completamente configurado
    if all(config.values()):
        print("\n✓ Configuración SMTP completa")
        return True
    else:
        print("\n✗ Configuración SMTP incompleta")
        return False

def test_email_send():
    """Intenta enviar un email de prueba"""
    if not test_smtp_config():
        print("\n❌ No se puede probar el envío sin configuración completa")
        return False
    
    print("\n" + "=" * 50)
    print("PRUEBA DE ENVÍO DE EMAIL")
    print("=" * 50)
    
    try:
        from senders import send_email
        
        # Email de prueba
        test_to = os.getenv('SMTP_USER')  # Enviarse a sí mismo
        test_subject = "Prueba de Sistema de Notificaciones - Toscana"
        test_html = """
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #795547;">✓ Prueba de Sistema de Notificaciones</h2>
                <p>Este es un email de prueba del sistema de facturación.</p>
                <p><strong>Si recibes este mensaje, las notificaciones están funcionando correctamente.</strong></p>
                <hr>
                <p style="font-size: 12px; color: #666;">
                    Sistema de Gestión - Toscana<br>
                    Enviado desde: {from_email}
                </p>
            </body>
        </html>
        """.format(from_email=os.getenv('SMTP_FROM'))
        
        print(f"\nIntentando enviar email de prueba a: {test_to}")
        send_email(test_to, test_subject, test_html)
        
        print(f"\n✓ Email enviado exitosamente a {test_to}")
        print("  Verifica tu bandeja de entrada (puede tardar unos segundos)")
        return True
        
    except Exception as e:
        print(f"\n✗ Error al enviar email: {e}")
        print("\nPosibles causas:")
        print("  - Credenciales SMTP incorrectas")
        print("  - Firewall bloqueando conexión")
        print("  - Puerto SMTP incorrecto")
        print("  - Gmail requiere 'App Password' si tienes 2FA activado")
        return False

if __name__ == '__main__':
    print("\n🔧 PRUEBA DE SISTEMA DE NOTIFICACIONES\n")
    
    # Primero verificar configuración
    config_ok = test_smtp_config()
    
    if config_ok:
        print("\n¿Deseas enviar un email de prueba? (s/n): ", end='')
        try:
            response = input().strip().lower()
            if response == 's':
                test_email_send()
        except:
            print("\nPrueba cancelada")
    
    print("\n" + "=" * 50)
    print("Prueba completada")
    print("=" * 50 + "\n")
