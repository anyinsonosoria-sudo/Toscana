#!/usr/bin/env python3
"""Corrección completa de codificación en todos los archivos HTML"""

import os
import re

# Mapa completo de reemplazos
replacements = {
    # Casos específicos encontrados
    'Gesti칩n': 'Gestión',
    'Estad칤sticas': 'Estadísticas',
    'R치pidas': 'Rápidas',
    'Estad‚àö‚â†sticas': 'Estadísticas',
    
    # Vocales acentuadas minúsculas
    '√°': 'á', '√©': 'é', '√≠': 'í', '√≥': 'ó', '√ļ': 'ú',
    '√º': 'ú',
    
    # Vocales acentuadas mayúsculas
    '√Å': 'Á', '√â': 'É', '√ã': 'Í', '√ì': 'Ó', '√ö': 'Ú',
    
    # Ñ
    '√±': 'ñ', '√Ñ': 'Ñ',
    
    # Signos de puntuación
    '¬ø': '¿', '¬°': '¡',
    
    # Caracteres especiales
    'üóëÔ∏è': '❌',
    'ûï': '➕',
    '‚àö‚â†': 'í',
    '‚â†': 'í',
    '‚àö': 'í',
    
    # Coreano (caracteres mal codificados como coreano)
    '칩': 'ó',
    '칤': 'í',
    '치': 'á',
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
all_changes = {}

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
                file_changes.append(f'{repr(old)} → {repr(new)} ({count}x)')
                total_replacements += count
                
                # Guardar para resumen global
                if old not in all_changes:
                    all_changes[old] = []
                all_changes[old].append((os.path.basename(html_file), count))
        
        # Si hubo cambios, guardar
        if content != original_content:
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(content)
            total_files_fixed += 1
            print(f'✅ {os.path.basename(html_file)}:')
            for change in file_changes[:5]:  # Mostrar primeros 5
                print(f'   • {change}')
            if len(file_changes) > 5:
                print(f'   ... y {len(file_changes) - 5} más')
            print()
    
    except Exception as e:
        print(f'❌ Error en {html_file}: {e}')

print('='*70)
print(f'📊 RESUMEN:')
print(f'   ✓ Archivos corregidos: {total_files_fixed}')
print(f'   ✓ Total de reemplazos: {total_replacements}')
print('='*70)

if all_changes:
    print('\n📝 Cambios más comunes:')
    for old, files in sorted(all_changes.items(), key=lambda x: sum(c for _, c in x[1]), reverse=True)[:10]:
        total = sum(c for _, c in files)
        print(f'   {repr(old)} → en {len(files)} archivo(s), {total} veces')

if total_files_fixed > 0:
    print('\n🔄 Reinicia el servidor Flask para ver los cambios.')
else:
    print('\n✅ No se encontraron archivos con problemas.')
