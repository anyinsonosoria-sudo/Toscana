#!/usr/bin/env python
"""Test para verificar el menú actualizado"""

from app import app

with app.app_context():
    with app.test_request_context():
        menu = app.jinja_env.globals['get_sidebar_menu']()
        
        print('=' * 60)
        print('MENÚ ACTUALIZADO')
        print('=' * 60)
        
        for item in menu:
            if item['key'] == 'billing':
                print(f"\n{item['label']}:")
                for child in item['children']:
                    print(f"  ✓ {child['label']}")
                    print(f"    URL: {child['url']}")
                    print()
        
        print('=' * 60)
        print('NOTA: "Cuentas por Cobrar" fue eliminada del menú.')
        print('Ahora "Facturas y Pagos" incluye toda la funcionalidad.')
        print('=' * 60)
