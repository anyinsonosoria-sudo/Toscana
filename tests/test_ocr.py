"""
Script de prueba para verificar funcionalidad OCR
"""

import sys
from pathlib import Path

def test_imports():
    """Verifica que todos los módulos se pueden importar"""
    print("Verificando imports...")
    try:
        from ocr_processing import ReceiptOCR, check_tesseract_available
        print("✓ ocr_processing importado correctamente")
    except ImportError as e:
        print(f"✗ Error importando ocr_processing: {e}")
        return False
    
    try:
        from PIL import Image
        print("✓ Pillow importado correctamente")
    except ImportError as e:
        print(f"✗ Error importando Pillow: {e}")
        return False
    
    try:
        import pytesseract
        print("✓ pytesseract importado correctamente")
    except ImportError as e:
        print(f"✗ Error importando pytesseract: {e}")
        return False
    
    return True

def test_tesseract():
    """Verifica que Tesseract está disponible"""
    print("\nVerificando Tesseract-OCR...")
    try:
        from ocr_processing import check_tesseract_available
        available, message = check_tesseract_available()
        if available:
            print(f"✓ {message}")
            return True
        else:
            print(f"✗ {message}")
            print("\nPara instalar Tesseract:")
            print("  Windows: https://github.com/UB-Mannheim/tesseract/wiki")
            print("  macOS: brew install tesseract")
            print("  Linux: sudo apt-get install tesseract-ocr")
            return False
    except Exception as e:
        print(f"✗ Error verificando Tesseract: {e}")
        return False

def test_ocr_processing():
    """Prueba funciones OCR básicas"""
    print("\nProbando funciones OCR...")
    try:
        from ocr_processing import ReceiptOCR
        
        # Probar extracción de cantidad
        test_text = "TOTAL: 1.234,56"
        amount = ReceiptOCR._extract_amount(test_text)
        if amount == 1234.56:
            print(f"✓ Extracción de monto funciona (extraído: {amount})")
        else:
            print(f"⚠ Extracción de monto: esperaba 1234.56, obtuvo {amount}")
        
        # Probar extracción de fecha
        test_text = "Fecha: 09/01/2024"
        date = ReceiptOCR._extract_date(test_text)
        if date:
            print(f"✓ Extracción de fecha funciona (extraído: {date})")
        else:
            print(f"⚠ Extracción de fecha: no se pudo extraer")
        
        # Probar cálculo de confianza
        test_text = "EMPRESA ABC\n09/01/2024\nMonto: 500.00\nTotal: 500.00"
        confidence = ReceiptOCR._calculate_confidence(test_text)
        print(f"✓ Cálculo de confianza funciona (nivel: {confidence:.0%})")
        
        return True
    except Exception as e:
        print(f"✗ Error en pruebas OCR: {e}")
        return False

def test_file_structure():
    """Verifica que la estructura de carpetas sea correcta"""
    print("\nVerificando estructura de carpetas...")
    
    uploads_dir = Path("static/uploads")
    if not uploads_dir.exists():
        print(f"⚠ Carpeta {uploads_dir} no existe, se creará automáticamente")
    else:
        print(f"✓ Carpeta {uploads_dir} existe")
    
    # Verificar archivos necesarios
    necessary_files = [
        "ocr_processing.py",
        "ocr_setup.py",
        "expenses.py",
        "app.py",
        "templates/gastos.html"
    ]
    
    all_exist = True
    for file in necessary_files:
        if Path(file).exists():
            print(f"✓ {file} existe")
        else:
            print(f"✗ {file} no encontrado")
            all_exist = False
    
    return all_exist

def main():
    print("="*70)
    print("TEST DE CONFIGURACIÓN OCR")
    print("="*70)
    print()
    
    # Ejecutar tests
    tests = [
        ("Imports", test_imports),
        ("Tesseract-OCR", test_tesseract),
        ("Procesamiento OCR", test_ocr_processing),
        ("Estructura de carpetas", test_file_structure),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ Error en test '{test_name}': {e}")
            results[test_name] = False
    
    # Resumen
    print("\n" + "="*70)
    print("RESUMEN DE TESTS")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✓ PASADO" if passed else "✗ FALLIDO"
        print(f"{test_name:.<50} {status}")
    
    all_passed = all(results.values())
    print()
    
    if all_passed:
        print("✓ Sistema OCR listo para usar!")
        print("\nAcceso: http://localhost:5000/gastos")
        return 0
    else:
        print("✗ Hay problemas a resolver. Ver arriba para más detalles.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
