#!/usr/bin/env python3
"""Escanear y corregir todos los archivos HTML con problemas de codificación"""

import os

# Mapa completo de reemplazos
replacements = {
    # Vocales acentuadas
    '√°': 'á', '√©': 'é', '√≠': 'í', '√≥': 'ó', '√ļ': 'ú',
    '√Å': 'Á', '√â': 'É', '√ã': 'Í', '√ì': 'Ó', '√ö': 'Ú',
    # Ñ
    '√±': 'ñ', '√Ñ': 'Ñ',
    # Signos de puntuación
    '¬ø': '¿', '¬°': '¡',
    # Otros caracteres comunes
    'üóëÔ∏è': '❌',
    'ûï': '➕',
    '∫': '∫',
    'º': 'º',
    '™': '™',
    '√': '',  # Este es problemático, revisar contexto
    # Caracteres específicos vistos
    'Gesti^√≥n': 'Gestión',
    '^√≥n': 'ón',
    '^√≠': 'í',
}

# Buscar todos los archivos HTML
html_files = []
for root, dirs, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            html_files.append(os.path.join(root, file))

print(f'🔍 Escaneando {len(html_files)} archivos HTML...\n')

total_files_fixed = 0
total_replacements = 0

for html_file in html_files:
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        file_changes = []
        
        # Aplicar reemplazos
        for old, new in replacements.items():
            count = content.count(old)
            if count > 0:
                content = content.replace(old, new)
                file_changes.append(f'{old} → {new} ({count}x)')
                total_replacements += count
        
        # Si hubo cambios, guardar
        if content != original_content:
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(content)
            total_files_fixed += 1
            print(f'✅ {os.path.basename(html_file)}:')
            for change in file_changes:
                print(f'   • {change}')
            print()
    
    except Exception as e:
        print(f'❌ Error en {html_file}: {e}')

print('='*70)
print(f'📊 RESUMEN:')
print(f'   ✓ Archivos corregidos: {total_files_fixed}')
print(f'   ✓ Total de reemplazos: {total_replacements}')
print('='*70)

if total_files_fixed > 0:
    print('\n🔄 Reinicia el servidor Flask para ver los cambios.')
else:
    print('\n✅ No se encontraron archivos con problemas.')
