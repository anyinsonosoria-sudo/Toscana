#!/usr/bin/env python
"""
Script de prueba para verificar que todos los módulos funcionan correctamente
"""
import db
import suppliers
import expenses
import accounting
import apartments
import residents
from datetime import datetime

def test_suppliers():
    """Probar módulo de suplidores"""
    print("\n=== PROBANDO MÓDULO DE SUPLIDORES ===")
    try:
        # Agregar suplidor
        sup_id = suppliers.add_supplier(
            name="Ferretería Central",
            contact_name="Juan Pérez",
            email="juan@ferreteria.com",
            phone="809-555-1234",
            address="Av. Principal #123",
            tax_id="123-456789-0"
        )
        print(f"✅ Suplidor agregado con ID: {sup_id}")
        
        # Listar suplidores
        sup_list = suppliers.list_suppliers()
        print(f"✅ Total de suplidores: {len(sup_list)}")
        
        # Obtener suplidor
        sup = suppliers.get_supplier(sup_id)
        print(f"✅ Suplidor obtenido: {sup['name']}")
        
        # Actualizar suplidor
        suppliers.update_supplier(sup_id, phone="809-555-9999")
        print(f"✅ Suplidor actualizado")
        
        return True
    except Exception as e:
        print(f"❌ Error en suplidores: {e}")
        return False

def test_expenses():
    """Probar módulo de gastos"""
    print("\n=== PROBANDO MÓDULO DE GASTOS ===")
    try:
        # Obtener suplidores para usar en gastos
        sup_list = suppliers.list_suppliers()
        supplier_id = sup_list[0]['id'] if sup_list else None
        
        # Agregar gasto
        exp_id = expenses.add_expense(
            description="Compra de materiales",
            amount=1500.00,
            category="Mantenimiento",
            supplier_id=supplier_id,
            date=datetime.now().strftime("%Y-%m-%d"),
            payment_method="Transferencia",
            notes="Reparación de techo"
        )
        print(f"✅ Gasto agregado con ID: {exp_id}")
        
        # Listar gastos
        exp_list = expenses.list_expenses()
        print(f"✅ Total de gastos: {len(exp_list)}")
        
        # Obtener gasto
        exp = expenses.get_expense(exp_id)
        print(f"✅ Gasto obtenido: {exp['description']}")
        
        # Actualizar gasto
        expenses.update_expense(exp_id, amount=1600.00)
        print(f"✅ Gasto actualizado")
        
        return True
    except Exception as e:
        print(f"❌ Error en gastos: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_accounting():
    """Probar módulo de contabilidad"""
    print("\n=== PROBANDO MÓDULO DE CONTABILIDAD ===")
    try:
        # Agregar ingreso
        income_id = accounting.add_transaction(
            transaction_type="income",
            description="Cuota de mantenimiento - Apt 1A",
            amount=2000.00,
            category="Cuotas de Mantenimiento",
            reference="FAC-001",
            date=datetime.now().strftime("%Y-%m-%d"),
            notes="Pago del mes actual"
        )
        print(f"✅ Ingreso agregado con ID: {income_id}")
        
        # Agregar egreso
        expense_id = accounting.add_transaction(
            transaction_type="expense",
            description="Pago de electricidad",
            amount=500.00,
            category="Servicios Públicos",
            reference="FAC-002",
            date=datetime.now().strftime("%Y-%m-%d")
        )
        print(f"✅ Egreso agregado con ID: {expense_id}")
        
        # Listar transacciones
        txn_list = accounting.list_transactions()
        print(f"✅ Total de transacciones: {len(txn_list)}")
        
        # Obtener balance
        balance = accounting.get_balance_summary()
        print(f"✅ Balance obtenido:")
        print(f"   - Ingresos: ${balance['total_income']:.2f}")
        print(f"   - Egresos: ${balance['total_expenses']:.2f}")
        print(f"   - Balance: ${balance['balance']:.2f}")
        
        return True
    except Exception as e:
        print(f"❌ Error en contabilidad: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_apartments():
    """Probar módulo de apartamentos"""
    print("\n=== PROBANDO MÓDULO DE APARTAMENTOS ===")
    try:
        # Agregar apartamento
        apt_id = apartments.add_apartment(
            number="101",
            floor="1",
            notes="Propietario: María González, Email: maria@email.com, Teléfono: 809-555-5555"
        )
        print(f"✅ Apartamento agregado con ID: {apt_id}")
        
        # Listar apartamentos
        apt_list = apartments.list_apartments()
        print(f"✅ Total de apartamentos: {len(apt_list)}")
        
        return True
    except Exception as e:
        print(f"❌ Error en apartamentos: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_residents():
    """Probar módulo de residentes"""
    print("\n=== PROBANDO MÓDULO DE RESIDENTES ===")
    try:
        # Obtener unidades (apartamentos en la tabla units)
        from models import list_units
        units = list_units()
        unit_id = units[0]['id'] if units else None
        
        if not unit_id:
            print("⚠️  No hay unidades disponibles para asignar residentes")
            return True
        
        # Agregar residente
        res_id = residents.add_resident(
            unit_id=unit_id,
            name="Carlos Rodríguez",
            role="Propietario",
            email="carlos@email.com",
            phone="809-555-7777"
        )
        print(f"✅ Residente agregado con ID: {res_id}")
        
        # Listar residentes
        res_list = residents.list_residents()
        print(f"✅ Total de residentes: {len(res_list)}")
        
        return True
    except Exception as e:
        print(f"❌ Error en residentes: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal de prueba"""
    print("\n" + "="*60)
    print("INICIANDO PRUEBAS DE MÓDULOS")
    print("="*60)
    
    # Inicializar base de datos
    print("\n=== INICIALIZANDO BASE DE DATOS ===")
    try:
        db.init_db()
        print("✅ Base de datos inicializada")
    except Exception as e:
        print(f"❌ Error al inicializar base de datos: {e}")
        return
    
    # Ejecutar pruebas
    results = {
        "Suplidores": test_suppliers(),
        "Gastos": test_expenses(),
        "Contabilidad": test_accounting(),
        "Apartamentos": test_apartments(),
        "Residentes": test_residents()
    }
    
    # Resumen
    print("\n" + "="*60)
    print("RESUMEN DE PRUEBAS")
    print("="*60)
    
    for module, result in results.items():
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"{module}: {status}")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} módulos pasaron las pruebas")
    
    if passed == total:
        print("\n🎉 ¡TODAS LAS PRUEBAS PASARON EXITOSAMENTE!")
    else:
        print("\n⚠️  Algunas pruebas fallaron. Revisa los errores arriba.")

if __name__ == "__main__":
    main()
