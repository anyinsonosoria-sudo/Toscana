"""
Script de instalación y actualización de dependencias
Instala todas las librerías necesarias para la Etapa 1 de seguridad
"""

import subprocess
import sys
from pathlib import Path

def run_command(command, description):
    """Ejecuta un comando y muestra resultado"""
    print(f"\n{'='*60}")
    print(f"📦 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ Éxito!")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stderr:
            print(e.stderr)
        return False

def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║  INSTALACIÓN DE DEPENDENCIAS - ETAPA 1: SEGURIDAD       ║
    ║  Building Maintenance System v2.0                        ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Verificar que requirements.txt existe
    req_file = Path(__file__).parent / "requirements.txt"
    if not req_file.exists():
        print("❌ Error: No se encontró requirements.txt")
        return False
    
    # Actualizar pip
    if not run_command(
        f"{sys.executable} -m pip install --upgrade pip",
        "Actualizando pip..."
    ):
        print("⚠️  Advertencia: No se pudo actualizar pip, continuando...")
    
    # Instalar dependencias
    if not run_command(
        f"{sys.executable} -m pip install -r requirements.txt",
        "Instalando dependencias de requirements.txt..."
    ):
        print("❌ Error instalando dependencias")
        return False
    
    print("""
    \n✅ INSTALACIÓN COMPLETADA
    
    📋 Próximos pasos:
    
    1. Crear archivo .env:
       > copy .env.example .env
       > Editar .env con tus configuraciones
    
    2. Ejecutar migración de base de datos:
       > python setup_database.py
    
    3. Iniciar aplicación:
       > python app.py
    
    4. Acceder al sistema:
       URL: http://localhost:5000
       Usuario: admin
       Contraseña: admin123
    
    ⚠️  IMPORTANTE: Cambiar la contraseña del admin en el primer login!
    """)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
