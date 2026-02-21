"""Probar check_password directamente"""
import user_model

print("Obteniendo usuario admin...")
user = user_model.get_user_by_username('admin')

if user:
    print(f"Usuario encontrado: {user.username}")
    print(f"Hash: {user.password_hash[:30]}...")
    print(f"\nProbando password 'admin123':")
    
    try:
        result = user.check_password('admin123')
        print(f"Resultado: {result}")
        if result:
            print("✅ PASSWORD CORRECTO")
        else:
            print("❌ PASSWORD INCORRECTO")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
else:
    print("❌ Usuario admin no encontrado")
