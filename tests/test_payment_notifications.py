"""
Script para probar el envío de notificaciones de pago
"""
import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
import models
import company
from apartments import get_apartment
from residents import list_by_unit

def test_payment_notification():
    """Prueba el envío de notificaciones"""
    print("=== Probando Envío de Notificaciones de Pago ===\n")
    
    # Obtener información de la empresa
    company_info = company.get_company_info()
    print(f"✓ Empresa: {company_info.get('name', 'N/A')}")
    print(f"✓ Email Admin: {company_info.get('email', 'N/A')}\n")
    
    # Obtener una factura pendiente
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT i.*, 
               COALESCE(SUM(p.amount), 0) as paid_amount
        FROM invoices i
        LEFT JOIN payments p ON i.id = p.invoice_id
        WHERE i.paid = 0
        GROUP BY i.id
        LIMIT 1
    """)
    invoice = cur.fetchone()
    
    if not invoice:
        print("❌ No hay facturas pendientes para probar")
        conn.close()
        return
    
    invoice = dict(invoice)
    pending_amount = invoice['amount'] - invoice['paid_amount']
    
    print(f"✓ Factura #{invoice['id']}")
    print(f"  - Monto total: RD${invoice['amount']:.2f}")
    print(f"  - Pagado: RD${invoice['paid_amount']:.2f}")
    print(f"  - Pendiente: RD${pending_amount:.2f}\n")
    
    # Obtener información del apartamento y residente
    apt = get_apartment(invoice['unit_id'])
    resident = None
    if apt:
        print(f"✓ Apartamento: {apt.get('number', 'N/A')}")
        residents = list_by_unit(apt['id'])
        if residents:
            resident = residents[0]
            print(f"✓ Residente: {resident.get('name', 'N/A')}")
            print(f"✓ Email Cliente: {resident.get('email', 'N/A')}\n")
        else:
            print("⚠ No se encontró residente para este apartamento\n")
    else:
        print("⚠ No se encontró apartamento\n")
    
    conn.close()
    
    # Mostrar instrucciones
    print("=" * 60)
    print("INSTRUCCIONES PARA PROBAR:")
    print("=" * 60)
    print("1. Ve a la interfaz web (Facturación o Registrar Pago)")
    print(f"2. Registra un pago para la Factura #{invoice['id']}")
    print("3. Asegúrate de marcar 'Enviar comprobante por email'")
    print("4. Verifica que lleguen los emails a:")
    print(f"   - Cliente: {resident.get('email', 'N/A') if apt and resident else 'N/A'}")
    print(f"   - Admin: {company_info.get('email', 'N/A')}")
    print("\n5. Para probar con estado de cuenta:")
    print("   - Marca también 'Adjuntar estado de cuenta del cliente'")
    print("   - Verifica que el PDF del estado de cuenta esté adjunto")
    print("\n6. Para probar el cálculo de cambio:")
    print("   - Selecciona método 'Efectivo'")
    print("   - Ingresa una cantidad mayor al monto a pagar")
    print("   - Verifica que aparezca el cambio a devolver")
    print("=" * 60)

if __name__ == "__main__":
    test_payment_notification()
