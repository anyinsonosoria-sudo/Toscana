"""
Settings (Configuración) Blueprint
Permite ver y editar la configuración general del sistema (empresa y personalización).
"""
from datetime import datetime
from pathlib import Path

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

import db
import company
import customization
import reports
from extensions import cache
from utils.decorators import admin_required, audit_log

settings_bp = Blueprint('settings', __name__, url_prefix='/configuracion')


def _get_database_tools_context():
    """Contexto UI para el módulo admin de snapshot/restore."""
    if not current_user.is_authenticated or not current_user.is_admin():
        return None

    max_content_length = current_app.config.get('MAX_CONTENT_LENGTH') or 0
    return {
        'enabled': True,
        'backup_enabled': current_app.config.get('WEB_DB_BACKUP_ENABLED', True),
        'restore_enabled': current_app.config.get('WEB_DB_RESTORE_ENABLED', False),
        'restore_confirmation_text': current_app.config.get('WEB_DB_RESTORE_CONFIRM_TEXT', 'RESTAURAR'),
        'db_info': db.get_db_file_info(),
        'snapshot_dir': str(db.DEFAULT_SNAPSHOT_DIR.resolve()),
        'upload_limit_mb': round(max_content_length / (1024 * 1024), 2) if max_content_length else None,
        'environment': current_app.config.get('ENV') or 'production' if current_app.config.get('SESSION_COOKIE_SECURE') else 'development',
    }


def _get_monthly_report_settings_context(company_info: dict | None = None):
    if not current_user.is_authenticated or not current_user.is_admin():
        return None

    company_info = company_info or {}
    monthly_report_settings = reports.get_monthly_report_settings(current_app.config)
    company_email = (company_info.get('email') or '').strip().lower()
    monthly_report_settings['fallback_admin_email'] = company_email
    monthly_report_settings['resolved_admin_email'] = (
        monthly_report_settings.get('admin_email') or company_email
    )
    return monthly_report_settings

@settings_bp.route('/', endpoint='view')
@login_required
# Puedes agregar un decorador de permisos aquí si lo deseas
# @permission_required('configuracion.view')
def configuracion_view():
    try:
        company_info = company.get_company_info() or {}
    except Exception:
        company_info = {}
    try:
        custom_settings = customization.get_settings_with_defaults()
        # Add sidebar_menu_order for the template
        default_menus = [
            {
                "key": "gestion",
                "label": "Gestión",
                "icon": "bi bi-folder",
                "type": "dropdown",
                "children": [
                    {
                        "key": "gestion_apartamentos",
                        "label": "Apartamentos",
                        "icon": "bi bi-building",
                        "url": "/apartamentos/",
                        "endpoint": "apartments.list"
                    },
                    {
                        "key": "gestion_productos",
                        "label": "Productos/Servicios",
                        "icon": "bi bi-box-seam",
                        "url": "/productos/",
                        "endpoint": "products.list"
                    },
                    {
                        "key": "gestion_proveedores",
                        "label": "Proveedores",
                        "icon": "bi bi-truck",
                        "url": "/suplidores/",
                        "endpoint": "suppliers.list"
                    }
                ]
            },
            {
                "key": "billing",
                "label": "Ventas",
                "icon": "bi bi-receipt",
                "type": "dropdown",
                "children": [
                    {
                        "key": "billing_facturas",
                        "label": "Facturas",
                        "icon": "bi bi-file-earmark-text",
                        "url": "/ventas/facturas",
                        "endpoint": "billing.invoices"
                    },
                    {
                        "key": "billing_pagos",
                        "label": "Pagos",
                        "icon": "bi bi-cash-coin",
                        "url": "/ventas/pagos",
                        "endpoint": "billing.payments"
                    },
                    {
                        "key": "billing_cuentas_cobrar",
                        "label": "Cuentas por Cobrar",
                        "icon": "bi bi-clipboard-check",
                        "url": "/ventas/cuentas-cobrar",
                        "endpoint": "billing.accounts_receivable"
                    },
                    {
                        "key": "billing_recurrentes",
                        "label": "Facturas Recurrentes",
                        "icon": "bi bi-arrow-repeat",
                        "url": "/ventas/recurrentes",
                        "endpoint": "billing.recurring_sales"
                    }
                ]
            },
            {
                "key": "accounting",
                "label": "Contabilidad",
                "icon": "bi bi-calculator",
                "url": "/contabilidad/",
                "endpoint": "accounting.view",
                "type": "single"
            },
            {
                "key": "expenses",
                "label": "Gastos",
                "icon": "bi bi-cash-stack",
                "url": "/gastos/",
                "endpoint": "expenses.view",
                "type": "single"
            },
            {
                "key": "reports",
                "label": "Reportes",
                "icon": "bi bi-graph-up",
                "url": "/reportes/",
                "endpoint": "reports.view",
                "type": "single"
            },
            {
                "key": "settings",
                "label": "Configuración",
                "icon": "bi bi-gear",
                "url": "/configuracion/",
                "endpoint": "settings.view",
                "type": "single"
            }
        ]
        custom_settings['sidebar_menu_order'] = customization.get_sidebar_menu_order(default_menus)
    except Exception:
        custom_settings = {}
    db_tools = _get_database_tools_context()
    monthly_report_settings = _get_monthly_report_settings_context(company_info)
    return render_template(
        'configuracion.html',
        company=company_info,
        customization=custom_settings,
        db_tools=db_tools,
        monthly_report_settings=monthly_report_settings,
        monthly_report_preview_reference_date=datetime.now().strftime('%Y-%m-%d'),
    )


# Guardar personalización visual
@settings_bp.route('/update_customization', methods=['POST'])
@login_required
def update_customization():
    accent_color = request.form.get('accent_color', '#795547')
    invoice_template = request.form.get('invoice_template', 'modern')
    display_logo = '1' if request.form.get('display_logo') == '1' else '0'
    customization.set_setting('accent_color', accent_color)
    customization.set_setting('invoice_template', invoice_template)
    customization.set_setting('display_logo', display_logo)
    flash('Personalización actualizada.', 'success')
    return redirect(url_for('settings.view'))

# Guardar orden del menú lateral
@settings_bp.route('/update_sidebar_order', methods=['POST'])
@login_required
def update_sidebar_order():
    order_mode = request.form.get('sidebar_order_mode', 'custom')
    menu_order = request.form.getlist('sidebar_menu_order[]')
    import json
    customization.set_setting('sidebar_order_mode', order_mode)
    customization.set_setting('sidebar_menu_order', json.dumps(menu_order))
    # Limpiar cache después de actualizar
    cache.clear()
    flash('Orden del menú lateral actualizado.', 'success')
    return redirect(url_for('settings.view'))


@settings_bp.route('/monthly-report/update', methods=['POST'])
@login_required
@admin_required
@audit_log('monthly_report.settings.update', 'Actualizar configuración del reporte mensual automático')
def update_monthly_report_settings():
    monthly_report_enabled = '1' if request.form.get('monthly_report_enabled') == '1' else '0'
    monthly_report_admin_only = '1' if request.form.get('monthly_report_admin_only') == '1' else '0'
    monthly_report_admin_email = (request.form.get('monthly_report_admin_email') or '').strip().lower()

    if monthly_report_admin_email and '@' not in monthly_report_admin_email:
        flash('El correo del administrador para el reporte mensual no es válido.', 'error')
        return redirect(url_for('settings.view'))

    customization.set_setting('monthly_financial_report_enabled', monthly_report_enabled)
    customization.set_setting('monthly_financial_report_admin_only', monthly_report_admin_only)
    customization.set_setting('monthly_financial_report_admin_email', monthly_report_admin_email)
    cache.clear()

    flash('Configuración del reporte mensual automático actualizada.', 'success')
    return redirect(url_for('settings.view'))

# Endpoint para limpiar cache manualmente
@settings_bp.route('/clear_cache', methods=['POST'])
@login_required
def clear_cache():
    """Limpia el cache de la aplicación"""
    cache.clear()
    flash('Cache limpiado correctamente.', 'success')
    return redirect(url_for('settings.view'))


@settings_bp.route('/database/backup', methods=['POST'])
@login_required
@admin_required
@audit_log('database.backup', 'Crear y descargar snapshot SQLite')
def download_database_snapshot():
    """Genera y descarga un backup consistente de la base actual."""
    if not current_app.config.get('WEB_DB_BACKUP_ENABLED', True):
        flash('La creación de backups desde la web está deshabilitada.', 'warning')
        return redirect(url_for('settings.view'))

    try:
        snapshot_path = db.create_snapshot()
        current_app.logger.info(
            'Backup web creado por %s: %s',
            current_user.username,
            snapshot_path,
        )
        return send_file(
            snapshot_path,
            as_attachment=True,
            download_name=snapshot_path.name,
            mimetype='application/octet-stream',
            max_age=0,
        )
    except Exception as exc:
        current_app.logger.error('Error creando backup web: %s', exc)
        flash(f'No se pudo crear el backup: {exc}', 'error')
        return redirect(url_for('settings.view'))


@settings_bp.route('/database/restore', methods=['POST'])
@login_required
@admin_required
@audit_log('database.restore', 'Restaurar snapshot SQLite')
def restore_database_snapshot():
    """Restaura una copia SQLite subida desde la interfaz web."""
    if not current_app.config.get('WEB_DB_RESTORE_ENABLED', False):
        flash('La restauración desde la web está deshabilitada en este entorno.', 'warning')
        return redirect(url_for('settings.view'))

    expected_confirmation = str(
        current_app.config.get('WEB_DB_RESTORE_CONFIRM_TEXT', 'RESTAURAR')
    ).strip().upper()
    provided_confirmation = (request.form.get('restore_confirmation') or '').strip().upper()
    if provided_confirmation != expected_confirmation:
        flash(
            f'Debes escribir "{expected_confirmation}" para confirmar la restauración.',
            'error',
        )
        return redirect(url_for('settings.view'))

    snapshot_file = request.files.get('snapshot_file')
    if not snapshot_file or not snapshot_file.filename:
        flash('Debes seleccionar un archivo SQLite para restaurar.', 'error')
        return redirect(url_for('settings.view'))

    filename = secure_filename(Path(snapshot_file.filename).name)
    file_suffix = Path(filename).suffix.lower()
    if file_suffix not in db.SNAPSHOT_EXTENSIONS:
        flash('Formato no permitido. Usa un archivo .sqlite, .sqlite3 o .db.', 'error')
        return redirect(url_for('settings.view'))

    upload_dir = db.DEFAULT_SNAPSHOT_DIR / 'incoming'
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f'upload-{datetime.now():%Y%m%d-%H%M%S}-{filename}'

    try:
        snapshot_file.save(upload_path)
        result = db.restore_snapshot(upload_path)
        cache.clear()
        current_app.logger.info(
            'Snapshot restaurado por %s sobre %s',
            current_user.username,
            result['target_path'],
        )
        if result['backup_path']:
            flash(
                f'Base de datos restaurada correctamente. Respaldo previo: {Path(result["backup_path"]).name}',
                'success',
            )
        else:
            flash('Base de datos restaurada correctamente.', 'success')
    except PermissionError:
        flash(
            'No se pudo reemplazar la base local. Cierra otros procesos que la estén usando e intenta de nuevo.',
            'error',
        )
    except Exception as exc:
        current_app.logger.error('Error restaurando snapshot web: %s', exc)
        flash(f'No se pudo restaurar la base: {exc}', 'error')
    finally:
        if upload_path.exists():
            try:
                upload_path.unlink()
            except PermissionError:
                current_app.logger.warning(
                    'No se pudo limpiar el snapshot subido inmediatamente: %s',
                    upload_path,
                )

    return redirect(url_for('settings.view'))
