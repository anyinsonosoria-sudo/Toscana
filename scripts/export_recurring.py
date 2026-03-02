"""Exportar ventas recurrentes de la BD local para insertar en PythonAnywhere"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db import get_db

with get_db() as conn:
    cur = conn.cursor()
    cur.execute("""SELECT id, unit_id, service_id, amount, frequency, billing_day, 
                          billing_time, start_date, end_date, description, active 
                   FROM recurring_sales ORDER BY id""")
    rows = cur.fetchall()
    print(f"Ventas recurrentes en BD local: {len(rows)}\n")
    
    if not rows:
        print("No hay ventas recurrentes en la BD local.")
    else:
        # Generar SQL para insertar en PythonAnywhere
        print("-- SQL para ejecutar en PythonAnywhere:")
        for r in rows:
            d = dict(r)
            print(f"  #{d['id']}: unit_id={d['unit_id']}, amount={d['amount']}, freq={d['frequency']}, day={d['billing_day']}, desc={d['description']}")
        
        print("\n-- Script Python para PythonAnywhere:")
        print("from db import get_db")
        print("with get_db() as conn:")
        print("    cur = conn.cursor()")
        for r in rows:
            d = dict(r)
            end = f"'{d['end_date']}'" if d['end_date'] else 'None'
            svc = d['service_id'] if d['service_id'] else 'None'
            bt = d['billing_time'] or '08:00'
            desc = (d['description'] or '').replace("'", "''")
            print(f"    cur.execute(\"INSERT INTO recurring_sales (unit_id, service_id, amount, frequency, billing_day, billing_time, start_date, end_date, description, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\", ({d['unit_id']}, {svc}, {d['amount']}, '{d['frequency']}', {d['billing_day']}, '{bt}', '{d['start_date']}', {end}, '{desc}', {d['active']}))")
        print("    conn.commit()")
        print("    print('Insertadas', cur.rowcount, 'ventas recurrentes')")
