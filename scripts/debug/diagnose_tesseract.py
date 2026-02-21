"""
Script de diagnóstico para Tesseract-OCR
Detecta problemas con la instalación y proporciona soluciones
"""

import sys
import os
import subprocess
from pathlib import Path

def find_tesseract():
    """Busca Tesseract en ubicaciones comunes"""
    common_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\tools\tesseract\tesseract.exe',
        os.path.expandvars(r'%USERPROFILE%\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'),
    ]
    
    print("=" * 70)
    print("BÚSQUEDA DE TESSERACT-OCR")
    print("=" * 70)
    
    for path in common_paths:
        exists = Path(path).exists()
        status = "✓ ENCONTRADO" if exists else "✗ No encontrado"
        print(f"{status}: {path}")
        if exists:
            return path
    
    return None

def test_pytesseract():
    """Prueba pytesseract"""
    print("\n" + "=" * 70)
    print("VERIFICACIÓN DE PYTESSERACT")
    print("=" * 70)
    
    try:
        import pytesseract
        print("✓ pytesseract está instalado")
        
        # Intentar obtener versión
        try:
            version = pytesseract.get_tesseract_version()
            print(f"✓ Versión de Tesseract detectada: {version}")
            return True
        except Exception as e:
            print(f"✗ No se pudo detectar Tesseract: {str(e)}")
            return False
    except ImportError:
        print("✗ pytesseract NO está instalado")
        print("  Instala con: pip install pytesseract")
        return False

def test_pil():
    """Prueba PIL"""
    print("\n" + "=" * 70)
    print("VERIFICACIÓN DE PILLOW")
    print("=" * 70)
    
    try:
        from PIL import Image
        print("✓ Pillow (PIL) está instalado")
        return True
    except ImportError:
        print("✗ Pillow NO está instalado")
        print("  Instala con: pip install Pillow")
        return False

def main():
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " DIAGNÓSTICO DE INSTALACIÓN - OCR PARA RECIBOS DE GASTOS ".center(68) + "║")
    print("╚" + "=" * 68 + "╝")
    
    # Buscar Tesseract
    tesseract_path = find_tesseract()
    
    # Verificar dependencias Python
    pil_ok = test_pil()
    pytesseract_ok = test_pytesseract()
    
    # Resumen
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    
    if not tesseract_path:
        print("\n⚠️  TESSERACT NO ENCONTRADO")
        print("\n📥 INSTALACIÓN REQUERIDA:")
        print("""
1. Ve a: https://github.com/UB-Mannheim/tesseract/wiki/Downloads
2. Descarga el instalador para Windows (última versión)
3. Ejecuta el instalador aceptando la ruta por defecto:
   C:\\Program Files\\Tesseract-OCR\\
4. Reinicia la aplicación Flask
5. Corre nuevamente este script

O en PowerShell (si tienes chocolatey):
   choco install tesseract

O con scoop:
   scoop install tesseract
        """)
    else:
        print(f"\n✓ Tesseract encontrado en: {tesseract_path}")
        
        if pytesseract_ok:
            print("✓ Sistema listo para usar OCR")
        else:
            print("\n⚠️  pytesseract no detecta Tesseract")
            print("   Solución: Reinicia la aplicación Flask")
    
    print("\n" + "=" * 70)
    print("\nPara más ayuda, consulta: QUICK_START.txt")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
