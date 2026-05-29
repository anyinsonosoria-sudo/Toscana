import pytest
from io import BytesIO
import db
import user_model

def test_profile_edit_and_photo_upload(auth_client, app):
    """Prueba el flujo de edición de perfil y carga de foto para un usuario autenticado"""
    # 1. GET para cargar la página del perfil
    response = auth_client.get('/auth/profile')
    assert response.status_code == 200
    assert b"Mi Perfil Personal" in response.data
    assert b"Nombre de Usuario" in response.data

    # 2. POST actualizando nombre, teléfono y cargando una foto falsa
    fake_image_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATu\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    fake_image_file = (BytesIO(fake_image_data), "avatar.png")
    
    post_data = {
        'full_name': 'Juan Pérez Residente',
        'phone': '809-555-0199',
        'profile_photo': fake_image_file
    }
    
    response = auth_client.post(
        '/auth/profile',
        data=post_data,
        content_type='multipart/form-data',
        follow_redirects=True
    )
    
    assert response.status_code == 200
    html_response = response.data.decode('utf-8')
    assert "Perfil actualizado con" in html_response or "exito" in html_response.lower() or "éxito" in html_response

    # 3. Comprobar que en la base de datos se guardaron los datos y la ruta de la foto
    with app.app_context():
        conn = db.get_conn()
        cur = conn.cursor()
        # El fixture auth_client por defecto inicia sesión como el usuario 'admin'
        cur.execute("SELECT full_name, phone, photo_url FROM users WHERE username = 'admin'")
        row = cur.fetchone()
        conn.close()
        
        assert row is not None
        assert row['full_name'] == 'Juan Pérez Residente'
        assert row['phone'] == '809-555-0199'
        assert row['photo_url'] is not None
        assert "user_" in row['photo_url']
        assert row['photo_url'].endswith(".png")

        # 4. Limpieza del archivo creado para no dejar basura en el repositorio de test
        try:
            import os
            from pathlib import Path
            img_path = Path(__file__).parent.parent / row['photo_url'].lstrip('/')
            if img_path.exists():
                img_path.unlink()
        except Exception:
            pass
