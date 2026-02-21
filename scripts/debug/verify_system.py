"""
Script de verificación rápida del sistema
Verifica que todos los módulos principales importen correctamente
"""

print("=" * 60)
print("VERIFICACIÓN DEL SISTEMA")
print("=" * 60)

modules_to_test = [
    ('app', 'Aplicación principal'),
    ('db', 'Base de datos'),
    ('config', 'Configuración'),
    ('models', 'Modelos de negocio'),
    ('billing', 'Módulo de facturación'),
    ('user_model', 'Modelo de usuarios'),
    ('auth', 'Autenticación'),
    ('extensions', 'Extensiones Flask'),
]

success = 0
failed = 0

for module_name, description in modules_to_test:
    try:
        __import__(module_name)
        print(f"✅ {description:30s} - OK")
        success += 1
    except Exception as e:
        print(f"❌ {description:30s} - ERROR: {e}")
        failed += 1

print("=" * 60)
print(f"Resultado: {success} éxitos, {failed} fallos")
print("=" * 60)

if failed == 0:
    print("✅ ¡Todos los módulos principales están funcionando!")
else:
    print(f"⚠️  {failed} módulos tienen problemas")
