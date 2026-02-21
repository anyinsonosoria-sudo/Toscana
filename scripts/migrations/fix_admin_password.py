"""Regenerar usuario admin con password correcto"""
import sqlite3
import bcrypt

# Generar nuevo hash para 'admin123'
password = 'admin123'
password_bytes = password.encode('utf-8')
salt = bcrypt.gensalt()
hash_bytes = bcrypt.hashpw(password_bytes, salt)
password_hash = hash_bytes.decode('utf-8')

print(f"Nuevo hash generado: {password_hash[:30]}...")

# Actualizar en la base de datos
conn = sqlite3.connect('data.db')
cursor = conn.cursor()

cursor.execute("""
    UPDATE users 
    SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
    WHERE username = 'admin'
""", (password_hash,))

conn.commit()
print(f"\n✅ Usuario 'admin' actualizado con password 'admin123'")
print(f"   Rows affected: {cursor.rowcount}")

conn.close()

# Verificar
print("\nVerificando...")
import user_model
user = user_model.get_user_by_username('admin')
if user.check_password('admin123'):
    print("✅ VERIFICACIÓN EXITOSA - Password funciona correctamente")
else:
    print("❌ VERIFICACIÓN FALLIDA")
