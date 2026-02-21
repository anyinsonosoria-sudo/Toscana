"""
Script de limpieza automática de ventas recurrentes y residentes para Xpack
"""
import db
from residents import list_residents, update_resident
from models import list_units, list_recurring_sales

conn = db.get_conn()
cur = conn.cursor()

# 1. Obtener residentes válidos
residents = list_residents()
units = list_units()
valid_resident_ids = set(r['id'] for r in residents)
valid_unit_ids = set(u['id'] for u in units)

# 2. Limpiar ventas recurrentes con resident_id inválido
recurring_sales = list_recurring_sales()
for sale in recurring_sales:
    if sale['resident_id'] not in valid_resident_ids:
        # Reasignar a primer residente válido
        new_id = residents[0]['id'] if residents else None
        if new_id:
            cur.execute('UPDATE recurring_sales SET resident_id=? WHERE id=?', (new_id, sale['id']))
            print(f"Venta recurrente {sale['id']} reasignada a residente {new_id}")
        else:
            cur.execute('DELETE FROM recurring_sales WHERE id=?', (sale['id'],))
            print(f"Venta recurrente {sale['id']} eliminada (sin residentes válidos)")

conn.commit()

# 3. Asegurar que cada residente tenga unit_id y email
for r in residents:
    update_needed = False
    fields = {}
    if not r.get('unit_id') and units:
        fields['unit_id'] = units[0]['id']
        update_needed = True
    if not r.get('email'):
        fields['email'] = 'anyinson.osoria@gmail.com'
        update_needed = True
    if update_needed:
        update_resident(r['id'], **fields)
        print(f"Residente {r['id']} actualizado: {fields}")

conn.close()
print("Limpieza completada. Puedes volver a probar la generación de facturas recurrentes.")
