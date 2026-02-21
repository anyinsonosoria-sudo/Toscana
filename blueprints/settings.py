"""
Settings (Configuración) Blueprint
Permite ver y editar la configuración general del sistema (empresa y personalización).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
import company
import customization

settings_bp = Blueprint('settings', __name__, url_prefix='/configuracion')

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
    return render_template('configuracion.html', company=company_info, customization=custom_settings)


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
    from extensions import cache
    cache.clear()
    flash('Orden del menú lateral actualizado.', 'success')
    return redirect(url_for('settings.view'))

# Endpoint para limpiar cache manualmente
@settings_bp.route('/clear_cache', methods=['POST'])
@login_required
def clear_cache():
    """Limpia el cache de la aplicación"""
    from extensions import cache
    cache.clear()
    flash('Cache limpiado correctamente.', 'success')
    return redirect(url_for('settings.view'))
