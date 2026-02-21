"""
Script de Organización del Proyecto
====================================
Mueve archivos huérfanos a carpetas apropiadas para mantener 
una estructura limpia y organizada.

Uso: python scripts/organize_project.py
"""

import os
import shutil
from pathlib import Path

# Directorio base
BASE_DIR = Path(__file__).parent.parent

# ==========================================
# DEFINICIÓN DE ARCHIVOS A ORGANIZAR
# ==========================================

# Archivos de fix/migración -> scripts/migrations/
FIX_MIGRATION_FILES = [
    'fix_admin_password.py',
    'fix_all_encoding.py',
    'fix_all_html.py',
    'fix_all_templates.py',
    'fix_database.py',
    'fix_db_receipts.py',
    'fix_encoding.py',
    'fix_facturacion.py',
    'fix_recurring_data.py',
    'migrate_apartments.py',
    'migrate_db.py',
    'migrate_products_services.py',
    'apply_company_migration.py',
    'run_migration.py',
    'create_users_table.py',
    'setup_database.py',
    'setup_logo.py',
    'setup_permissions.py',
    'sync_accounting.py',
    'CORRECCION_COMPLETA.py',
]

# Archivos de test dispersos -> tests/
TEST_FILES = [
    'test_ajax_headers.py',
    'test_blueprints.py',
    'test_clear_decimals.py',
    'test_correct_url.py',
    'test_currency_format.py',
    'test_full_ocr.py',
    'test_improved_ocr.py',
    'test_login_simple.py',
    'test_logo_invoice.py',
    'test_modules.py',
    'test_ocr.py',
    'test_ocr_endpoint.py',
    'test_ocr_endpoint2.py',
    'test_ocr_final.py',
    'test_ocr_full.py',
    'test_ocr_modal.py',
    'test_ocr_save.py',
    'test_ocr_simple.py',
    'test_ocr_with_csrf.py',
    'test_password.py',
    'test_payment_notifications.py',
    'test_payment_receipt.py',
    'test_performance.py',
    'test_permissions_integration.py',
    'test_rate_limiting.py',
    'test_server.py',
    'test_validations.py',
    'test_view_receipt.py',
    'test_with_text.py',
    'run_tests.py',
    'run_tests_simple.py',
]

# Archivos de diagnóstico/debug -> scripts/debug/
DEBUG_FILES = [
    'debug_ocr.py',
    'diagnose_tesseract.py',
    'check_billing_endpoints.py',
    'check_encoding.py',
    'check_users.py',
    'database_report.py',
    'validate_endpoints.py',
    'verify_accounting_data.py',
    'verify_server.py',
]

# Documentación -> docs/
DOC_FILES = [
    'AUDITORIA_TECNICA_COMPLETA.md',
    'CHECKLIST.txt',
    'CONFIGURACION_NOTIFICACIONES.txt',
    'ETAPA1_INSTALACION.md',
    'ETAPA2_PLAN.md',
    'EXECUTIVE_SUMMARY.txt',
    'FASE1.2_RESUMEN.md',
    'FASE2.2_PERMISOS.md',
    'FASE2.3_RATE_LIMITING.md',
    'FASE2.4_PERFORMANCE.md',
    'FASE_2.6_TESTING.md',
    'FEATURE_VER_RECIBO.txt',
    'FIX_UPLOAD_ISSUE.txt',
    'INDEX.txt',
    'LAUNCHER_README.md',
    'MODULO_EMPRESA.md',
    'OCR_README.md',
    'OCR_SYSTEM.md',
    'PASO_4_COMPLETADO.md',
    'QUICK_START.txt',
    'RESUMEN_REVISION.md',
    'SISTEMA_PERMISOS.md',
    'SOLUCION_COMPLETA_OCR.txt',
    'SOLUCION_TESSERACT.txt',
    'STEP_BY_STEP_GUIDE.txt',
    'SYSTEM_DIAGRAM.txt',
    'TECHNICAL_SUMMARY.txt',
    'TESTING_RESULTADOS.md',
    'TESTING_RESUMEN.md',
    'WHATSAPP_CONFIG.md',
]

# Archivos legacy (backup, old) -> legacy/
LEGACY_FILES = [
    'config_old.py',
    'main_backup.py',
    'main.py',  # Si existe app.py, main.py es legacy
]

# Archivos de instalación -> scripts/setup/
SETUP_FILES = [
    'install_dependencies.py',
    'download_tesseract_lang.py',
    'ocr_setup.py',
    'patch_whatsapp.py',
]


def create_directories():
    """Crea las carpetas necesarias si no existen."""
    dirs = [
        BASE_DIR / 'scripts' / 'migrations',
        BASE_DIR / 'scripts' / 'debug',
        BASE_DIR / 'scripts' / 'setup',
        BASE_DIR / 'docs',
        BASE_DIR / 'docs' / 'guides',
        BASE_DIR / 'docs' / 'technical',
        BASE_DIR / 'legacy',
        BASE_DIR / 'tests',
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Directorio creado/verificado: {d.relative_to(BASE_DIR)}")
    
    return True


def move_files(file_list, dest_dir, dry_run=True):
    """
    Mueve archivos a un directorio destino.
    
    Args:
        file_list: Lista de nombres de archivos
        dest_dir: Directorio destino
        dry_run: Si es True, solo muestra qué haría
    """
    moved = 0
    skipped = 0
    
    for filename in file_list:
        src = BASE_DIR / filename
        dst = dest_dir / filename
        
        if not src.exists():
            # print(f"[SKIP] No existe: {filename}")
            skipped += 1
            continue
        
        if dst.exists():
            print(f"[SKIP] Ya existe en destino: {filename}")
            skipped += 1
            continue
        
        if dry_run:
            print(f"[DRY-RUN] Mover: {filename} -> {dest_dir.relative_to(BASE_DIR)}/")
        else:
            try:
                shutil.move(str(src), str(dst))
                print(f"[OK] Movido: {filename} -> {dest_dir.relative_to(BASE_DIR)}/")
                moved += 1
            except Exception as e:
                print(f"[ERROR] No se pudo mover {filename}: {e}")
    
    return moved, skipped


def organize_project(dry_run=True):
    """
    Organiza todos los archivos del proyecto.
    
    Args:
        dry_run: Si es True, solo muestra qué haría sin mover archivos
    """
    print("=" * 60)
    print("ORGANIZACIÓN DEL PROYECTO")
    print("=" * 60)
    
    if dry_run:
        print("\n⚠️  MODO DRY-RUN: Solo se muestra qué se movería")
        print("    Para ejecutar realmente, usa: organize_project(dry_run=False)\n")
    
    # Crear directorios
    print("\n[1] Creando directorios...")
    create_directories()
    
    # Mover archivos de fix/migración
    print("\n[2] Archivos de Fix/Migración -> scripts/migrations/")
    move_files(FIX_MIGRATION_FILES, BASE_DIR / 'scripts' / 'migrations', dry_run)
    
    # Mover archivos de test
    print("\n[3] Archivos de Test -> tests/")
    move_files(TEST_FILES, BASE_DIR / 'tests', dry_run)
    
    # Mover archivos de debug
    print("\n[4] Archivos de Debug -> scripts/debug/")
    move_files(DEBUG_FILES, BASE_DIR / 'scripts' / 'debug', dry_run)
    
    # Mover documentación
    print("\n[5] Documentación -> docs/")
    move_files(DOC_FILES, BASE_DIR / 'docs', dry_run)
    
    # Mover archivos legacy
    print("\n[6] Archivos Legacy -> legacy/")
    move_files(LEGACY_FILES, BASE_DIR / 'legacy', dry_run)
    
    # Mover archivos de setup
    print("\n[7] Archivos de Setup -> scripts/setup/")
    move_files(SETUP_FILES, BASE_DIR / 'scripts' / 'setup', dry_run)
    
    print("\n" + "=" * 60)
    if dry_run:
        print("✅ Simulación completada. Revisa los cambios propuestos.")
        print("   Para ejecutar: python organize_project.py --execute")
    else:
        print("✅ Organización completada.")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    
    dry_run = "--execute" not in sys.argv
    organize_project(dry_run=dry_run)
