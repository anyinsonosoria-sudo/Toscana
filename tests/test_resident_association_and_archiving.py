import pytest
import json
import os
import db
import user_model
import apartments

def test_user_apartment_association_workflow(auth_client, app):
    with app.app_context():
        # Clean / setup test state
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM resident_user_units")
        cur.execute("DELETE FROM residents")
        cur.execute("DELETE FROM apartments")
        # Ensure we do not delete our acting admin user
        cur.execute("DELETE FROM users WHERE username != 'admin'")
        conn.commit()
        conn.close()

    # 1. Crear un apartamento
    apt_id = apartments.add_apartment(
        number="999",
        floor="9",
        resident_name="Temp Resident",
        resident_role="tenant",
        resident_email="",
        resident_phone="555-5555"
    )
    
    # 2. Registrar usuario de tipo residente asociando el apartamento
    response = auth_client.post('/auth/register', data={
        'username': 'resident_test',
        'email': 'resident_test@test.com',
        'password': 'password123',
        'password_confirm': 'password123',
        'full_name': 'Resident Test Name',
        'role': 'resident',
        'apartment_id': str(apt_id)
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = 'resident_test'")
    user_row = cur.fetchone()
    user_id = user_row['id']
    cur.execute("SELECT unit_id FROM resident_user_units WHERE user_id = ?", (user_id,))
    first_link_rows = cur.fetchall()
    conn.close()

    # Verificar que el apartamento ahora está asociado al email del nuevo residente
    apt = apartments.get_apartment(apt_id)
    assert apt['resident_email'] == 'resident_test@test.com'
    assert apt['resident_name'] == 'Resident Test Name'
    assert [row['unit_id'] for row in first_link_rows] == [apt_id]

    # 3. Editar usuario residente para asociar a otro nuevo apartamento
    apt_id2 = apartments.add_apartment(
        number="888",
        floor="8",
        resident_name="Another Temp",
        resident_role="tenant",
        resident_email="",
        resident_phone="444-4444"
    )
    
    response_edit = auth_client.post(f'/auth/users/{user_id}/edit', data={
        'full_name': 'Resident Updated',
        'email': 'resident_test@test.com',
        'role': 'resident',
        'apartment_id': str(apt_id2)
    }, follow_redirects=True)
    
    assert response_edit.status_code == 200
    
    # Verificar que se desvinculó del primero y se vinculó al segundo
    apt1 = apartments.get_apartment(apt_id)
    apt2 = apartments.get_apartment(apt_id2)

    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("SELECT unit_id FROM resident_user_units WHERE user_id = ? ORDER BY unit_id", (user_id,))
    current_link_rows = cur.fetchall()
    conn.close()
    
    assert apt1['resident_email'] is None or apt1['resident_email'] == ""
    assert apt2['resident_email'] == 'resident_test@test.com'
    assert apt2['resident_name'] == 'Resident Updated'
    assert [row['unit_id'] for row in current_link_rows] == [apt_id2]


def test_apartment_archiving_workflow(auth_client, app):
    with app.app_context():
        # Clean / setup test state
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM resident_user_units")
        cur.execute("DELETE FROM residents")
        cur.execute("DELETE FROM apartments")
        conn.commit()
        conn.close()

    # 1. Crear apartamento
    apt_id = apartments.add_apartment(
        number="777",
        floor="7",
        resident_name="Ghost Owner",
        resident_role="owner",
        resident_email="ghost@test.com",
        resident_phone="333-333"
    )
    
    # Agregar residente adicional
    apartments.save_extra_residents(apt_id, [
        {"name": "Extra 1", "role": "tenant", "email": "extra1@test.com", "phone": "111"}
    ])
    
    # 2. Agregar factura y pago
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO invoices (unit_id, description, amount, paid) VALUES (?, ?, ?, ?)",
                (apt_id, "Test maintenance fee", 200.0, 1))
    inv_id = cur.lastrowid
    cur.execute("INSERT INTO payments (invoice_id, amount, method) VALUES (?, ?, ?)",
                (inv_id, 200.0, "cash"))
    conn.commit()
    conn.close()
    
    # 3. Llamar al endpoint de archivar
    response = auth_client.post(f'/apartamentos/archive/{apt_id}', follow_redirects=True)
    assert response.status_code == 200
    
    # 4. Verificar BD después de archivar
    apt = apartments.get_apartment(apt_id)
    assert apt['resident_name'] is None or apt['resident_name'] == ""
    assert apt['resident_email'] is None or apt['resident_email'] == ""
    assert apt['resident_phone'] is None or apt['resident_phone'] == ""
    
    # Verificar que no hay residentes adicionales
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as count FROM residents WHERE unit_id = ?", (apt_id,))
    res_count = cur.fetchone()['count']
    assert res_count == 0
    
    # Verificar que no hay facturas
    cur.execute("SELECT COUNT(*) as count FROM invoices WHERE unit_id = ?", (apt_id,))
    inv_count = cur.fetchone()['count']
    assert inv_count == 0
    
    # Verificar que no hay pagos correspondientes a esa factura
    cur.execute("SELECT COUNT(*) as count FROM payments WHERE invoice_id = ?", (inv_id,))
    pay_count = cur.fetchone()['count']
    assert pay_count == 0
    conn.close()
    
    # 5. Comprobar que existe un archivo JSON de respaldo
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backups", "apartments")
    assert os.path.exists(backup_dir)
    files = os.listdir(backup_dir)
    backup_files = [f for f in files if f.startswith("apartment_777_") and f.endswith(".json")]
    assert len(backup_files) >= 1
    
    # Validar contenido de alguno de los archivos JSON de respaldo
    backup_path = os.path.join(backup_dir, backup_files[0])
    with open(backup_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data['apartment']['number'] == "777"
    assert data['apartment']['resident_name'] == "Ghost Owner"
    assert len(data['extra_residents']) == 1
    assert data['extra_residents'][0]['name'] == "Extra 1"
    assert len(data['invoices']) == 1
    assert data['invoices'][0]['description'] == "Test maintenance fee"
    assert len(data['payments']) == 1
    assert data['payments'][0]['amount'] == 200.0
