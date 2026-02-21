"""
Script de verificación de seguridad SQL
Busca posibles vulnerabilidades de SQL injection en el código
"""

import re
import os
from pathlib import Path

def check_sql_injection_vulnerabilities(base_path):
    """
    Verifica posibles vulnerabilidades de SQL injection en archivos Python
    """
    
    # Patrones peligrosos
    dangerous_patterns = [
        # Interpolación directa de strings en SQL
        r'execute\(["\'].*%s.*["\'].*%',  # % formatting
        r'execute\(f["\']',  # f-strings en execute
        r'execute\(["\'].*\+',  # concatenación con +
        r'execute\(["\'].*\.format',  # .format() en SQL
    ]
    
    # Archivos a verificar
    files_to_check = []
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.endswith('.py'):
                files_to_check.append(os.path.join(root, file))
    
    vulnerabilities = []
    
    for file_path in files_to_check:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    # Verificar cada patrón peligroso
                    for pattern in dangerous_patterns:
                        if re.search(pattern, line):
                            vulnerabilities.append({
                                'file': file_path,
                                'line': i,
                                'code': line.strip(),
                                'pattern': pattern,
                                'severity': 'CRITICAL'
                            })
                    
                    # Verificar concatenación de strings en execute
                    if 'execute(' in line and ('+' in line or '%' in line or 'format(' in line):
                        # Verificar que no sea un comentario
                        if not line.strip().startswith('#'):
                            vulnerabilities.append({
                                'file': file_path,
                                'line': i,
                                'code': line.strip(),
                                'pattern': 'String concatenation in execute()',
                                'severity': 'HIGH'
                            })
        except Exception as e:
            print(f"Error procesando {file_path}: {e}")
    
    return vulnerabilities


def main():
    import sys
    # Configurar encoding para Windows
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    base_path = Path(__file__).parent.parent
    print("=" * 80)
    print("VERIFICACION DE VULNERABILIDADES SQL INJECTION")
    print("=" * 80)
    
    vulnerabilities = check_sql_injection_vulnerabilities(base_path)
    
    if not vulnerabilities:
        print("\n[OK] No se encontraron vulnerabilidades evidentes de SQL injection")
        print("\nNOTA: Este script verifica patrones comunes pero no garantiza")
        print("      seguridad completa. Se recomienda:")
        print("      1. Siempre usar parametros en execute()")
        print("      2. Nunca interpolar variables del usuario directamente")
        print("      3. Validar y sanitizar todos los inputs")
    else:
        print(f"\n[ADVERTENCIA] Se encontraron {len(vulnerabilities)} posibles vulnerabilidades:\n")
        
        for vuln in vulnerabilities:
            rel_path = os.path.relpath(vuln['file'], base_path)
            print(f"[{vuln['severity']}] {rel_path}:{vuln['line']}")
            print(f"  Patron: {vuln['pattern']}")
            print(f"  Codigo: {vuln['code']}")
            print()
        
        print("\nRECOMENDACIONES:")
        print("   1. Usar siempre parametros: execute('SELECT * FROM table WHERE id=?', (id,))")
        print("   2. NUNCA usar: execute(f'SELECT * FROM table WHERE id={id}')")
        print("   3. NUNCA usar: execute('SELECT * FROM table WHERE id=%s' % id)")
        print("   4. Validar inputs del usuario antes de usarlos")
    
    print("\n" + "=" * 80)
    return len(vulnerabilities)


if __name__ == "__main__":
    exit(main())
