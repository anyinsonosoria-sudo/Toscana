"""
Setup script para instalar y configurar OCR
Verifica que Tesseract-OCR esté instalado y configura pytesseract
"""

import sys
import os
import subprocess
from pathlib import Path

def check_tesseract():
    """Verifica si Tesseract está instalado"""
    try:
        import pytesseract
        result = pytesseract.get_tesseract_version()
        print(f"✓ Tesseract OCR encontrado: {result}")
        return True
    except Exception as e:
        print(f"✗ Tesseract OCR no está instalado: {e}")
        return False

def check_python_packages():
    """Verifica que las dependencias Python estén instaladas"""
    packages = ['pillow', 'pytesseract', 'flask']
    missing = []
    
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✓ {package} instalado")
        except ImportError:
            print(f"✗ {package} no instalado")
            missing.append(package)
    
    return missing

def install_python_packages(packages):
    """Instala paquetes Python faltantes"""
    if not packages:
        return True
    
    print(f"\nInstalando paquetes: {', '.join(packages)}...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + packages)
        print("✓ Paquetes instalados correctamente")
        return True
    except Exception as e:
        print(f"✗ Error instalando paquetes: {e}")
        return False

def print_tesseract_install_instructions():
    """Imprime instrucciones para instalar Tesseract"""
    print("\n" + "="*70)
    print("INSTALACIÓN DE TESSERACT-OCR")
    print("="*70)
    
    if sys.platform == 'win32':
        print("""
Windows:
1. Descarga el instalador desde:
   https://github.com/UB-Mannheim/tesseract/wiki
   
2. Busca "tesseract-ocr-w64-v5.x.exe" (o la versión más reciente)

3. Ejecuta el instalador y acepta la instalación por defecto
   (Se instalará en: C:\\Program Files\\Tesseract-OCR)

4. Reinicia la aplicación Flask

Después de instalar, verifica con:
   python ocr_setup.py
""")
    elif sys.platform == 'darwin':
        print("""
macOS:
1. Instala con Homebrew:
   brew install tesseract

2. Verifica la instalación:
   which tesseract

3. Reinicia la aplicación Flask
""")
    else:  # Linux
        print("""
Linux (Ubuntu/Debian):
1. Instala Tesseract:
   sudo apt-get update
   sudo apt-get install tesseract-ocr

2. Verifica la instalación:
   which tesseract

3. Reinicia la aplicación Flask
""")

def main():
    print("="*70)
    print("CONFIGURACIÓN DE OCR PARA BUILDING MAINTENANCE")
    print("="*70)
    print()
    
    # Verificar paquetes Python
    print("Verificando dependencias Python...")
    missing_packages = check_python_packages()
    
    if missing_packages:
        print(f"\nPaquetes faltantes: {', '.join(missing_packages)}")
        if input("¿Deseas instalarlos ahora? (s/n): ").lower() == 's':
            if not install_python_packages(missing_packages):
                print("\nError: No se pudieron instalar los paquetes")
                return False
        else:
            return False
    
    print()
    
    # Verificar Tesseract
    print("Verificando Tesseract-OCR...")
    if check_tesseract():
        print("\n✓ Sistema OCR completamente configurado y listo")
        return True
    else:
        print_tesseract_install_instructions()
        print("\nPor favor instala Tesseract-OCR y ejecuta este script nuevamente.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
