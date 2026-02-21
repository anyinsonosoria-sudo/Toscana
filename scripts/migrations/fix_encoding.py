"""
Script para detectar y convertir archivos HTML a UTF-8
Soluciona el error UnicodeDecodeError
"""
import os
import chardet
from pathlib import Path

def detect_encoding(file_path):
    """Detecta la codificación de un archivo"""
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        return result['encoding'], result['confidence']

def convert_to_utf8(file_path, source_encoding):
    """Convierte un archivo a UTF-8"""
    try:
        # Leer con la codificación original
        with open(file_path, 'r', encoding=source_encoding, errors='ignore') as f:
            content = f.read()
        
        # Escribir en UTF-8
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"  ❌ Error convirtiendo {file_path}: {e}")
        return False

def fix_html_encoding():
    """Convierte todos los archivos HTML a UTF-8"""
    templates_dir = Path(__file__).parent / 'templates'
    
    if not templates_dir.exists():
        print("❌ No se encontró la carpeta templates/")
        return
    
    html_files = list(templates_dir.glob('*.html'))
    
    if not html_files:
        print("❌ No se encontraron archivos HTML")
        return
    
    print(f"\n🔍 Analizando {len(html_files)} archivos HTML...\n")
    
    converted = []
    already_utf8 = []
    errors = []
    
    for html_file in html_files:
        try:
            encoding, confidence = detect_encoding(html_file)
            
            if encoding and encoding.lower() in ['utf-8', 'ascii']:
                already_utf8.append(html_file.name)
                print(f"✅ {html_file.name}: Ya está en {encoding}")
            else:
                print(f"⚠️  {html_file.name}: {encoding} (confianza: {confidence:.0%})")
                
                # Intentar convertir
                if convert_to_utf8(html_file, encoding):
                    converted.append(html_file.name)
                    print(f"   ✓ Convertido a UTF-8")
                else:
                    errors.append(html_file.name)
        
        except Exception as e:
            print(f"❌ {html_file.name}: Error - {e}")
            errors.append(html_file.name)
    
    # Resumen
    print("\n" + "="*60)
    print("📊 RESUMEN")
    print("="*60)
    print(f"✅ Ya en UTF-8: {len(already_utf8)} archivos")
    print(f"🔄 Convertidos: {len(converted)} archivos")
    print(f"❌ Errores: {len(errors)} archivos")
    
    if converted:
        print("\n🔄 Archivos convertidos:")
        for filename in converted:
            print(f"   • {filename}")
    
    if errors:
        print("\n❌ Archivos con errores:")
        for filename in errors:
            print(f"   • {filename}")
    
    print("\n✅ Proceso completado. Reinicia el servidor Flask.\n")

if __name__ == "__main__":
    fix_html_encoding()
