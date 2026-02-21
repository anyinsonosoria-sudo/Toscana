#!/usr/bin/env python
"""
Descargar modelos de idioma para Tesseract
"""

import os
import urllib.request
import sys

def download_tesseract_language(lang_code='spa'):
    """Descarga el modelo de idioma para Tesseract"""
    
    tessdata_dir = r'C:\Users\anyinson.osoria\AppData\Local\Programs\Tesseract-OCR\tessdata'
    
    if not os.path.exists(tessdata_dir):
        print(f"❌ directorio tessdata no existe: {tessdata_dir}")
        return False
    
    traineddata_file = os.path.join(tessdata_dir, f'{lang_code}.traineddata')
    
    if os.path.exists(traineddata_file):
        print(f"✓ {lang_code}.traineddata ya está instalado")
        return True
    
    print(f"Descargando {lang_code}.traineddata...")
    print(f"Destino: {traineddata_file}")
    
    # URL del modelo de Tesseract (desde el repositorio oficial)
    urls = [
        f'https://github.com/tesseract-ocr/tessdata/raw/main/{lang_code}.traineddata',  # Repositorio oficial
        f'https://github.com/UB-Mannheim/tesseract/raw/main/tessdata/{lang_code}.traineddata',  # Backup
    ]
    
    try:
        for url in urls:
            try:
                print(f"Intenta descargando desde: {url}")
                urllib.request.urlretrieve(url, traineddata_file)
                print(f"✓ {lang_code}.traineddata descargado correctamente")
                print(f"  Tamaño: {os.path.getsize(traineddata_file) / 1024 / 1024:.2f} MB")
                return True
            except Exception as e:
                print(f"  ❌ Falló: {type(e).__name__}")
                continue
        
        raise Exception("Todas las URLs fallaron")
    except Exception as e:
        print(f"❌ Error al descargar {lang_code}.traineddata:")
        print(f"   {str(e)}")
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("DESCARGADOR DE MODELOS DE IDIOMA PARA TESSERACT")
    print("=" * 70)
    print()
    
    success = download_tesseract_language('spa')
    
    print()
    print("=" * 70)
    if success:
        print("✓ Instalación completada")
        print("  Ahora puedes usar OCR en español")
    else:
        print("❌ Hubo un error en la instalación")
        print("Intenta:")
        print("  1. Descargar manualmente desde GitHub:")
        print("     https://github.com/UB-Mannheim/tesseract/raw/main/tessdata/spa.traineddata")
        print("  2. Guardar en: " + r'C:\Users\anyinson.osoria\AppData\Local\Programs\Tesseract-OCR\tessdata')
    print("=" * 70)
    
    sys.exit(0 if success else 1)
