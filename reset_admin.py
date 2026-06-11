import os
import sqlite3
import bcrypt
import sys

# Asegurar que estamos en el directorio del script
os.chdir(os.path.dirname(os.path.abspath(__file__)))

db_path = os.path.join('data', 'data.db')
if not os.path.exists(db_path):
    print(f"La base de datos no existe en: {db_path}")
    try:
        import db
        db_path = str(db.DB_PATH)
        print(f"Ruta alternativa encontrada: {db_path}")
    except Exception:
        pass

if not os.path.exists(db_path):
    print("ERROR: No se encontró el archivo de base de datos sqlite.")
    sys.exit(1)

print(f"Conectando a la base de datos: {db_path}")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

try:
    # Verificar si la tabla de usuarios existe
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cur.fetchone():
        print("ERROR: La tabla 'users' no existe. Inicia la aplicación primero para crear las tablas.")
        conn.close()
        sys.exit(1)

    admin_username = 'admin'
    admin_email = 'admin@building.local'
    admin_password = 'admin123'

    admin_hash = bcrypt.hashpw(
        admin_password.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')

    # Eliminar al administrador viejo si existe
    cur.execute("DELETE FROM users WHERE username = ? OR email = ?", (admin_username, admin_email))

    # Insertar el nuevo con la contraseña restablecida
    cur.execute("""
        INSERT INTO users 
        (username, email, password_hash, full_name, role, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        admin_username,
        admin_email,
        admin_hash,
        'Administrador del Sistema',
        'admin',
        1
    ))

    conn.commit()
    print("============================================================")
    print("[OK] Usuario Administrador re-creado/restablecido con exito:")
    print(f"   Usuario: {admin_username}")
    print(f"   Email: {admin_email}")
    print(f"   Password: {admin_password}")
    print("============================================================")

except Exception as e:
    print(f"Ocurrio un error: {e}")
finally:
    conn.close()
