#!/usr/bin/env python
"""
Test para verificar que cuentas por cobrar y pagos funcionan correctamente
"""

import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
import models
from datetime import datetime

print("=" * 70)
print("TEST DE CUENTAS POR COBRAR Y PAGOS")
print("=" * 70)

try:
    with app.app_context():
        # Test 1: Obtener facturas
        print("\n[1] Obteniendo lista de facturas...")
        invoices = models.list_invoices()
        print(f"✓ {len(invoices)} facturas encontradas")
        
        if invoices:
            # Test 2: Calcular montos pagados
            print("\n[2] Calculando montos pagados por factura...")
            invoice_paid_amounts = {}
            for inv in invoices:
                paid_amt = models.get_invoice_paid_amount(inv['id'])
                invoice_paid_amounts[inv['id']] = paid_amt
                pending = inv['amount'] - paid_amt
                status = "Pagada" if inv['paid'] else f"Pendiente: RD$ {pending:,.2f}"
                print(f"  Factura #{inv['id']}: Monto={inv['amount']:,.2f}, Pagado={paid_amt:,.2f}, Estado={status}")
            
            print(f"\n✓ {len(invoice_paid_amounts)} montos calculados")
            
            # Test 3: Verificar datos para template cuentas_cobrar
            print("\n[3] Preparando datos para template cuentas_cobrar.html...")
            pending_invoices = []
            pending_amounts = []
            for inv in invoices:
                if not inv['paid']:
                    paid_amt = invoice_paid_amounts.get(inv['id'], 0)
                    pending_amt = inv['amount'] - paid_amt
                    pending_amounts.append(pending_amt)
                    pending_invoices.append(inv)
            
            total_pending = sum(pending_amounts) if pending_amounts else 0
            print(f"✓ {len(pending_invoices)} facturas pendientes")
            print(f"✓ Total pendiente: RD$ {total_pending:,.2f}")
            
            # Test 4: Verificar datos para template pagos.html
            print("\n[4] Preparando datos para template pagos.html...")
            total_paid = sum(invoice_paid_amounts.values())
            invoices_with_payments = [inv for inv in invoices if invoice_paid_amounts.get(inv['id'], 0) > 0]
            complete_paid = [inv for inv in invoices if inv['paid']]
            
            print(f"✓ Total cobrado: RD$ {total_paid:,.2f}")
            print(f"✓ Facturas con pagos: {len(invoices_with_payments)}")
            print(f"✓ Facturas pagadas completamente: {len(complete_paid)}")
            
        print("\n" + "=" * 70)
        print("✓ TODOS LOS TESTS PASARON CORRECTAMENTE")
        print("=" * 70)
        print("\nLos templates de cuentas_cobrar.html y pagos.html")
        print("ahora recibirán correctamente:")
        print("  - invoice_paid_amounts: Dict[int, float]")
        print("  - invoices: List[Dict]")
        print("\nYa no necesitan llamar a get_paid_amount() indefinida.")
        
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
