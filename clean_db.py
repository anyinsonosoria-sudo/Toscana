import os
import shutil

print("Limpiando archivos de migración incorrectos...")

if os.path.exists('migrations'):
    shutil.rmtree('migrations')
    print("- Carpeta 'migrations' eliminada.")

if os.path.exists('data.db'):
    os.remove('data.db')
    print("- Archivo 'data.db' vacío en la raíz eliminado.")

print("¡Limpieza completada! Ahora puedes re-inicializar la base de datos correcta.")
