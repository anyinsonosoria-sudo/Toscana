#!/usr/bin/env python3
"""Fix remaining encoding issues in facturacion.html"""

# Leer archivo
with open('templates/facturacion.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplazos específicos para caracteres mal codificados
replacements = {
    'Descripci√≥n': 'Descripción',
    'l√≠nea': 'línea',
    'üóëÔ∏è': '❌',
    'Notificaci√≥n': 'Notificación',
    'Tel√©fono': 'Teléfono',
    'L√≠neas': 'Líneas',
    '√≥': 'ó',
    '√≠': 'í',
    '√©': 'é',
    '√°': 'á',
    '√ļ': 'ú',
    '√±': 'ñ',
    '¬ø': '¿',
    '¬°': '¡',
}

# Aplicar reemplazos
changes_made = []
for old, new in replacements.items():
    count = content.count(old)
    if count > 0:
        content = content.replace(old, new)
        changes_made.append(f'{old} -> {new} ({count} veces)')

if changes_made:
    with open('templates/facturacion.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✅ Archivo corregido:')
    for change in changes_made:
        print(f'  ✓ {change}')
else:
    print('ℹ️ No se encontraron caracteres para reemplazar')
