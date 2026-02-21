#!/usr/bin/env python3
"""Verificar estado final de la codificación en todos los archivos HTML"""

import os

# Caracteres problemáticos conocidos
problem_chars = [
    '√', 'ü', '¬', 'Ô', '∏', '©', '™', '®', '‚', 'Œ', 'ƒ', '„', '…', '†', '‡', 
    'ˆ', '‰', 'Š', '‹', 'Ž', ''', ''', '"', '"', '•', '–', '—', '˜', 'š', '›', 
    'œ', 'ž', 'Ÿ', '칩', '칤', '치', '‚àö', '‚â†'
]

# Buscar todos los archivos HTML
html_files = []
for root, dirs, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            html_files.append(os.path.join(root, file))

print(f'🔍 Verificando {len(html_files)} archivos HTML...\n')

files_with_issues = {}
total_issues = 0

for html_file in html_files:
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        issues = []
        for line_num, line in enumerate(lines, 1):
            for char in problem_chars:
                if char in line:
                    issues.append((line_num, line.strip()[:100]))
                    break
        
        if issues:
            files_with_issues[os.path.basename(html_file)] = issues
            total_issues += len(issues)
    
    except Exception as e:
        print(f'❌ Error en {html_file}: {e}')

if files_with_issues:
    print('⚠️  Archivos con problemas restantes:\n')
    for filename, issues in sorted(files_with_issues.items()):
        print(f'📄 {filename}: {len(issues)} línea(s) con problemas')
        for line_num, content in issues[:3]:
            print(f'   Línea {line_num}: {content}')
        if len(issues) > 3:
            print(f'   ... y {len(issues) - 3} líneas más')
        print()
    
    print('='*70)
    print(f'📊 TOTAL: {len(files_with_issues)} archivo(s) con {total_issues} líneas problemáticas')
    print('='*70)
else:
    print('='*70)
    print('✅ ¡PERFECTO! Todos los archivos están correctamente codificados')
    print('='*70)
