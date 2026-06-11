import os
import shutil

if os.path.exists('migrations'):
    print("Renombrando carpeta 'migrations' a 'legacy_migrations'...")
    os.rename('migrations', 'legacy_migrations')
    print("¡Renombrado exitoso! Ahora puedes correr 'python -m flask db init'")
else:
    print("La carpeta 'migrations' ya no existe o ya fue renombrada.")
