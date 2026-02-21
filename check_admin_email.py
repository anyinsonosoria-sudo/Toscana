import sqlite3

conn = sqlite3.connect('data/data.db')
cur = conn.cursor()
cur.execute('SELECT name, email FROM company_info LIMIT 1')
row = cur.fetchone()

print('=== CONFIGURACION ACTUAL ===')
if row:
    print(f'Empresa: {row[0] or "Sin nombre"}')
    print(f'Email Admin: {row[1] or "NO CONFIGURADO"}')
else:
    print('Empresa: NO CONFIGURADA')
    print('Email Admin: NO CONFIGURADO')
    print('\nNECESITAS configurar la empresa:')
    print('1. Ve a http://localhost:5000/settings/empresa')
    print('2. Completa el nombre de la empresa y el email')
    
conn.close()
