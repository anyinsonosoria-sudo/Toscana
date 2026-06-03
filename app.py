"""
Aplicación principal Flask para gestión de edificios.
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import timedelta
from typing import Any, Optional
from dotenv import load_dotenv
import requests

# Cargar variables de entorno desde .env
load_dotenv()

from flask import Flask, redirect, url_for, render_template, jsonify, request, session
from flask_login import current_user, login_required

import db
import company
import customization
import residents
from extensions import init_extensions, scheduler
from auth import auth_bp
from blueprints.settings import settings_bp
from blueprints.company import company_bp
from blueprints.apartments import apartments_bp
from blueprints.billing import billing_bp
from blueprints.accounting import accounting_bp
from blueprints.expenses import expenses_bp
from blueprints.products import products_bp
from blueprints.reports import reports_bp
from blueprints.resident_api import resident_api_bp
from blueprints.suppliers import suppliers_bp


def create_app(config_object: Optional[str] = None) -> Flask:
    """Factory para crear la aplicación Flask."""
    app = Flask(__name__)
    
    # Configuración básica
    app.config['SECRET_KEY'] = os.environ.get(
        'SECRET_KEY', 
        os.environ.get('FLASK_SECRET_KEY', 'replace-this-with-a-secure-random-key')
    )
    
    # Cargar configuración
    if config_object:
        app.config.from_object(config_object)
    else:
        try:
            app.config.from_object('config')
        except Exception:
            pass
    
    # Configuraciones adicionales de seguridad
    app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
    app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')
    app.config.setdefault('PERMANENT_SESSION_LIFETIME', timedelta(hours=8))
    app.config.setdefault('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)  # 16MB max upload
    app.config.setdefault('SCHEDULER_TIMEZONE', 'America/Santo_Domingo')
    app.config.setdefault(
        'RESIDENT_API_JWT_SECRET',
        os.environ.get('RESIDENT_API_JWT_SECRET', '').strip() or app.config['SECRET_KEY'],
    )
    app.config.setdefault(
        'RESIDENT_API_JWT_ISSUER',
        os.environ.get('RESIDENT_API_JWT_ISSUER', 'toscana-resident-api').strip() or 'toscana-resident-api',
    )
    app.config.setdefault(
        'RESIDENT_API_ACCESS_TOKEN_MINUTES',
        int(os.environ.get('RESIDENT_API_ACCESS_TOKEN_MINUTES', '15')),
    )
    app.config.setdefault(
        'RESIDENT_API_REFRESH_TOKEN_DAYS',
        int(os.environ.get('RESIDENT_API_REFRESH_TOKEN_DAYS', '30')),
    )
    app.config.setdefault(
        'MONTHLY_FINANCIAL_REPORT_ENABLED',
        os.environ.get('MONTHLY_FINANCIAL_REPORT_ENABLED', '1').strip().lower() in {'1', 'true', 'yes', 'on'},
    )
    app.config.setdefault('MONTHLY_FINANCIAL_REPORT_HOUR', 6)
    app.config.setdefault('MONTHLY_FINANCIAL_REPORT_MINUTE', 0)
    app.config.setdefault(
        'MONTHLY_FINANCIAL_REPORT_ADMIN_ONLY',
        os.environ.get('MONTHLY_FINANCIAL_REPORT_ADMIN_ONLY', '').strip().lower() in {'1', 'true', 'yes', 'on'},
    )
    app.config.setdefault(
        'MONTHLY_FINANCIAL_REPORT_ADMIN_EMAIL',
        os.environ.get('MONTHLY_FINANCIAL_REPORT_ADMIN_EMAIL', '').strip(),
    )
    restore_enabled_default = os.environ.get('FLASK_ENV') != 'production'
    app.config.setdefault(
        'WEB_DB_BACKUP_ENABLED',
        os.environ.get('WEB_DB_BACKUP_ENABLED', '1').strip().lower() in {'1', 'true', 'yes', 'on'},
    )
    app.config.setdefault(
        'WEB_DB_RESTORE_ENABLED',
        os.environ.get(
            'WEB_DB_RESTORE_ENABLED',
            '1' if restore_enabled_default else '0',
        ).strip().lower() in {'1', 'true', 'yes', 'on'},
    )
    app.config.setdefault(
        'WEB_DB_RESTORE_CONFIRM_TEXT',
        os.environ.get('WEB_DB_RESTORE_CONFIRM_TEXT', 'RESTAURAR').strip() or 'RESTAURAR',
    )
    app.config.setdefault(
        'RESIDENT_AI_CHAT_ENABLED',
        os.environ.get('RESIDENT_AI_CHAT_ENABLED', '0').strip().lower() in {'1', 'true', 'yes', 'on'},
    )
    app.config.setdefault(
        'RESIDENT_AI_API_URL',
        os.environ.get('RESIDENT_AI_API_URL', 'https://api.openai.com/v1/chat/completions').strip(),
    )
    app.config.setdefault(
        'RESIDENT_AI_API_KEY',
        os.environ.get('RESIDENT_AI_API_KEY', '').strip(),
    )
    app.config.setdefault(
        'RESIDENT_AI_MODEL',
        os.environ.get('RESIDENT_AI_MODEL', 'gpt-4o-mini').strip() or 'gpt-4o-mini',
    )
    app.config.setdefault(
        'RESIDENT_AI_TIMEOUT_SECONDS',
        int(os.environ.get('RESIDENT_AI_TIMEOUT_SECONDS', '20')),
    )
    
    # Configurar carpeta de uploads
    upload_folder = Path(__file__).parent / 'static' / 'uploads'
    upload_folder.mkdir(parents=True, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = str(upload_folder)
    
    # En producción, requerir SECRET_KEY seguro
    if os.environ.get('FLASK_ENV') == 'production':
        if app.config.get('SECRET_KEY') == 'replace-this-with-a-secure-random-key':
            raise RuntimeError("SECRET_KEY inseguro. Configura una variable de entorno segura para producción.")
        app.config['SESSION_COOKIE_SECURE'] = True
    
    # Configurar logging
    _configure_logging(app)
    
    # Inicializar extensiones (CSRF, login, cache, limiter...)
    init_extensions(app)

    # Registrar tarea programada: generar facturas recurrentes cada día a las 00:05
    _register_scheduler_jobs(app)

    # Registrar blueprints
    _register_blueprints(app)
    
    # Registrar context processors
    _register_context_processors(app)
    
    # Registrar rutas principales
    _register_routes(app)
    
    # Registrar manejadores de errores
    _register_error_handlers(app)
    
    # Registrar headers de seguridad
    _register_security_headers(app)
    
    # Inicializar base de datos
    with app.app_context():
        try:
            db.init_db()
            app.logger.info("Base de datos inicializada correctamente")
        except Exception as e:
            app.logger.error(f"Error inicializando base de datos: {e}")
    
    return app


def _configure_logging(app: Flask) -> None:
    """Configura el sistema de logging."""
    # Crear directorio de logs si no existe
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(exist_ok=True)    
    # Configurar handler de archivo
    file_handler = RotatingFileHandler(
        log_dir / 'app.log',
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    
    if app.debug:
        file_handler.setLevel(logging.DEBUG)
        app.logger.setLevel(logging.DEBUG)
    else:
        file_handler.setLevel(logging.INFO)
        app.logger.setLevel(logging.INFO)
    
    app.logger.addHandler(file_handler)


def _register_scheduler_jobs(app: Flask) -> None:
    """Registra los trabajos periódicos del scheduler."""
    try:
        @scheduler.task(
            'interval',
            id='process_recurring_invoices',
            minutes=1,
            misfire_grace_time=60,
        )
        def _job_process_recurring():
            """Comprueba cada minuto si alguna factura recurrente debe generarse ahora."""
            with app.app_context():
                try:
                    import models
                    result = models.process_due_recurring_invoices()
                    if result['generated']:
                        app.logger.info(
                            f"[Scheduler] Facturas recurrentes: "
                            f"{len(result['generated'])} generadas, "
                            f"{len(result['skipped'])} omitidas, "
                            f"{len(result['errors'])} errores"
                        )
                    if result['errors']:
                        for err in result['errors']:
                            app.logger.error(f"[Scheduler] Error: {err}")
                except Exception as exc:
                    app.logger.error(f"[Scheduler] Fallo al procesar facturas recurrentes: {exc}")

        app.logger.info(
            "[OK] Tarea programada registrada: verificar facturas recurrentes cada minuto"
        )

        @scheduler.task(
            'cron',
            id='send_monthly_financial_report',
            day=1,
            hour=app.config.get('MONTHLY_FINANCIAL_REPORT_HOUR', 6),
            minute=app.config.get('MONTHLY_FINANCIAL_REPORT_MINUTE', 0),
            misfire_grace_time=43200,
        )
        def _job_send_monthly_financial_report():
            """Envía el reporte financiero consolidado del mes anterior."""
            with app.app_context():
                try:
                    from reports import dispatch_monthly_financial_report

                    result = dispatch_monthly_financial_report(
                        app_config=app.config,
                        respect_enabled_setting=True,
                    )
                    summary = result.get('summary', {})
                    app.logger.info(
                        "[Scheduler] %s | período=%s | solo admin=%s | admin=%s | enviados=%s | omitidos=%s | errores=%s",
                        summary.get('log_message', 'Reporte financiero mensual procesado.'),
                        result.get('report_period', 'N/A'),
                        result.get('admin_only', False),
                        result.get('resolved_admin_email', ''),
                        len(result.get('sent', [])),
                        len(result.get('skipped', [])),
                        len(result.get('failed', [])),
                    )
                except Exception as exc:
                    app.logger.error(f"[Scheduler] Fallo al enviar reporte financiero mensual: {exc}")

        app.logger.info(
            "[OK] Tarea programada registrada: reporte financiero mensual cada día 1 a las 06:00"
        )
    except Exception as e:
        app.logger.warning(f"[WARNING] No se pudo registrar la tarea del scheduler: {e}")


def _register_blueprints(app: Flask) -> None:
    """Registra todos los blueprints de la aplicación."""
    blueprints = [
        auth_bp,
        settings_bp,
        company_bp,
        apartments_bp,
        billing_bp,
        accounting_bp,
        expenses_bp,
        products_bp,
        reports_bp,
        resident_api_bp,
        suppliers_bp,
    ]
    
    for bp in blueprints:
        try:
            app.register_blueprint(bp)
            app.logger.debug(f"Blueprint registrado: {bp.name}")
        except Exception as e:
            app.logger.error(f"Error registrando blueprint {bp.name}: {e}")


def _register_context_processors(app: Flask) -> None:
    """Registra los context processors para templates."""
    
    @app.context_processor
    def inject_company_info():
        """Inyecta información de la empresa en todos los templates."""
        def get_company_info():
            try:
                return company.get_company_info()
            except Exception:
                return {}
        return dict(get_company_info=get_company_info)
    
    @app.context_processor
    def inject_accent_color():
        """Inyecta el color de acento en todos los templates."""
        def get_accent_color():
            try:
                return customization.get_setting('accent_color', '#795548')
            except Exception:
                return '#795548'
        return dict(get_accent_color=get_accent_color)
    
    @app.context_processor
    def inject_sidebar_menu():
        """Inyecta el menú del sidebar en todos los templates."""
        def get_sidebar_menu():
            # Residentes solo ven el ítem de Dashboard principal (que está fijo en el HTML)
            if current_user.is_authenticated and current_user.role == 'resident':
                return []
                
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
                            "key": "billing_registrar_pago",
                            "label": "Registrar Pago",
                            "icon": "bi bi-cash-coin",
                            "url": "/ventas/registrar-pago",
                            "endpoint": "billing.register_payment"
                        },
                        {
                            "key": "billing_historial_pagos",
                            "label": "Historial de Pagos",
                            "icon": "bi bi-clock-history",
                            "url": "/ventas/pagos",
                            "endpoint": "billing.payments"
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
                    "endpoint": "accounting.list",
                    "type": "single"
                },
                {
                    "key": "expenses",
                    "label": "Gastos",
                    "icon": "bi bi-cash-stack",
                    "url": "/gastos/",
                    "endpoint": "expenses.list",
                    "type": "single"
                },
                {
                    "key": "reports",
                    "label": "Reportes",
                    "icon": "bi bi-graph-up",
                    "url": "/reportes/",
                    "endpoint": "reports.list",
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
            try:
                return customization.get_sidebar_menu_order(default_menus)
            except Exception:
                return default_menus
        return dict(get_sidebar_menu=get_sidebar_menu)

    @app.context_processor
    def inject_resident_navigation():
        """Inyecta la navegación del portal residente."""
        def get_resident_navigation():
            return [
                {
                    'endpoint': 'resident_balances',
                    'label': 'Balances',
                    'icon': 'bi bi-wallet2',
                    'url': '/dashboard/balances',
                },
                {
                    'endpoint': 'resident_evolution',
                    'label': 'Evolución',
                    'icon': 'bi bi-graph-up-arrow',
                    'url': '/dashboard/evolucion',
                },
                {
                    'endpoint': 'resident_billing_overview',
                    'label': 'Facturas y pagos',
                    'icon': 'bi bi-receipt-cutoff',
                    'url': '/dashboard/facturas-pagos',
                },
                {
                    'endpoint': 'resident_reports',
                    'label': 'Reportes',
                    'icon': 'bi bi-file-earmark-bar-graph',
                    'url': '/dashboard/reportes',
                },
                {
                    'endpoint': 'resident_help',
                    'label': 'Ayuda',
                    'icon': 'bi bi-chat-square-dots',
                    'url': '/dashboard/ayuda',
                },
            ]

        return dict(get_resident_navigation=get_resident_navigation)
    
    @app.context_processor
    def inject_payment_helpers():
        """Inyecta funciones auxiliares para pagos."""
        def get_paid_amount(invoice_id):
            """Obtiene el monto total pagado de una factura."""
            try:
                conn = db.get_conn()
                cur = conn.cursor()
                cur.execute("SELECT IFNULL(SUM(amount),0) FROM payments WHERE invoice_id=?", (invoice_id,))
                result = cur.fetchone()
                conn.close()
                return result[0] if result else 0
            except Exception:
                return 0
        return dict(get_paid_amount=get_paid_amount)
    
    # Filtro de moneda
    @app.template_filter('currency')
    def currency_filter(amount):
        """Formatea montos con formato: $1,000.00"""
        if amount is None:
            amount = 0
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            amount = 0
        return f"${amount:,.2f}"


def _register_routes(app: Flask) -> None:
    """Registra las rutas principales de la aplicación."""
    
    @app.route("/")
    def index():
        """Ruta principal: redirige según autenticación."""
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        else:
            return redirect(url_for("auth.login"))

    resident_month_names = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    resident_month_lookup = {name.lower(): number for number, name in resident_month_names.items()}
    resident_month_short_names = {
        1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
    }

    def _build_resident_report_months():
        """Genera el histórico de reportes mensuales completos visibles para residentes."""
        from datetime import datetime

        months = []
        now = datetime.now()
        oldest_date_str = None
        try:
            conn = db.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT MIN(issued_date) FROM invoices")
            min_inv = cur.fetchone()[0]
            cur.execute("SELECT MIN(paid_date) FROM payments")
            min_pay = cur.fetchone()[0]
            conn.close()

            dates = []
            if min_inv:
                dates.append(min_inv[:7])
            if min_pay:
                dates.append(min_pay[:7])
            if dates:
                oldest_date_str = min(dates)
        except Exception as e:
            app.logger.error(f"Error finding start of operations for reports list: {e}")

        for offset in range(1, 7):
            month_value = now.month - offset
            year_value = now.year
            while month_value <= 0:
                month_value += 12
                year_value -= 1

            month_key = f"{year_value}-{month_value:02d}"
            if oldest_date_str and month_key < oldest_date_str:
                continue

            reference_year = year_value
            reference_month = month_value + 1
            if reference_month == 13:
                reference_month = 1
                reference_year += 1

            months.append({
                'label': f"{resident_month_names[month_value]} {year_value}",
                'ref_date': f"{reference_year}-{reference_month:02d}-01",
                'period_key': month_key,
            })

        return months

    def _format_resident_currency(amount):
        try:
            return f"RD$ {float(amount or 0):,.2f}"
        except (TypeError, ValueError):
            return "RD$ 0.00"

    def _format_resident_month_option(month_key: str):
        try:
            year_value, month_value = month_key.split('-', 1)
            month_number = int(month_value)
            return {
                'value': month_key,
                'label': f"{resident_month_names[month_number]} {year_value}",
            }
        except Exception:
            return {'value': month_key, 'label': month_key}

    def _get_resident_common_context():
        linked_apartments = residents.list_linked_apartments_for_user(
            current_user.id,
            fallback_email=current_user.email,
        )
        resident_summary = residents.get_resident_statement_summary_for_user(
            current_user.id,
            fallback_email=current_user.email,
        )
        return {
            'apartments': linked_apartments,
            'resident_summary': resident_summary,
            'resident_totals': resident_summary['totals'],
            'resident_units': resident_summary['apartments'],
            'company_info': company.get_company_info() or {},
            'report_months': _build_resident_report_months(),
        }

    def _build_resident_balances_context():
        context = _get_resident_common_context()
        context.update({
            'pending_preview': residents.list_resident_invoices_for_user(
                current_user.id,
                fallback_email=current_user.email,
                paid=False,
                limit=4,
            ),
        })
        return context

    def _build_resident_evolution_context():
        from datetime import datetime

        context = _get_resident_common_context()
        invoices = residents.list_resident_invoices_for_user(
            current_user.id,
            fallback_email=current_user.email,
        )
        payment_history: dict[str, Any] = residents.get_resident_payment_history_for_user(
            current_user.id,
            fallback_email=current_user.email,
            limit=None,
        )
        payment_items = list(payment_history.get('items') or [])

        trend_keys = []
        trend_labels = []
        trend_invoiced = {}
        trend_paid = {}
        now = datetime.now()

        for offset in range(5, -1, -1):
            month_value = now.month - offset
            year_value = now.year
            while month_value <= 0:
                month_value += 12
                year_value -= 1
            key = f"{year_value}-{month_value:02d}"
            trend_keys.append(key)
            trend_labels.append(f"{resident_month_short_names[month_value]} {year_value}")
            trend_invoiced[key] = 0.0
            trend_paid[key] = 0.0

        for invoice in invoices:
            month_key = (invoice.get('issued_date') or '')[:7]
            if month_key in trend_invoiced:
                trend_invoiced[month_key] += float(invoice.get('amount') or 0)

        for payment in payment_items:
            month_key = (payment.get('paid_date') or '')[:7]
            if month_key in trend_paid:
                trend_paid[month_key] += float(payment.get('amount') or 0)

        context.update({
            'trend_labels': trend_labels,
            'trend_invoiced_values': [trend_invoiced[key] for key in trend_keys],
            'trend_paid_values': [trend_paid[key] for key in trend_keys],
            'status_distribution_labels': ['Pendiente', 'Pagado'],
            'status_distribution_values': [
                float(context['resident_totals'].get('balance') or 0),
                float(context['resident_totals'].get('total_paid') or 0),
            ],
            'unit_balance_labels': [
                f"Apto {unit.get('apartment_number') or unit.get('unit_id')}" for unit in context['resident_units']
            ],
            'unit_balance_values': [float(unit.get('balance') or 0) for unit in context['resident_units']],
            'unit_paid_values': [float(unit.get('total_paid') or 0) for unit in context['resident_units']],
            'has_financial_activity': bool(invoices or payment_items),
        })
        return context

    def _build_resident_billing_context():
        context = _get_resident_common_context()
        page = max(request.args.get('page', type=int) or 1, 1)
        page_size = 6
        method_filter = (request.args.get('method') or '').strip()
        month_filter = (request.args.get('month') or '').strip()

        payment_history: dict[str, Any] = residents.get_resident_payment_history_for_user(
            current_user.id,
            fallback_email=current_user.email,
            method=method_filter or None,
            month=month_filter or None,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        payment_items = list(payment_history.get('items') or [])
        payment_total = int(payment_history.get('total') or 0)
        payment_methods = list(payment_history.get('methods') or [])
        payment_months = list(payment_history.get('months') or [])
        total_pages = max(1, (payment_total + page_size - 1) // page_size) if payment_total else 1

        context.update({
            'pending_invoices': residents.list_resident_invoices_for_user(
                current_user.id,
                fallback_email=current_user.email,
                paid=False,
            ),
            'payments_history': payment_items,
            'payments_total': payment_total,
            'payments_page': page,
            'payments_total_pages': total_pages,
            'payments_has_prev': page > 1,
            'payments_has_next': page < total_pages,
            'payment_filter_method': method_filter,
            'payment_filter_month': month_filter,
            'payment_filter_methods': payment_methods,
            'payment_filter_months': [
                _format_resident_month_option(month_key) for month_key in payment_months
            ],
        })
        return context

    def _build_resident_reports_context():
        from datetime import datetime

        context = _get_resident_common_context()
        context.update({
            'current_report_url': url_for(
                'reports.monthly_preview_pdf',
                reference_date=datetime.now().strftime('%Y-%m-%d'),
                period_mode='current_month_to_date',
            ),
        })
        return context

    def _extract_resident_month_reference(question: str):
        import re
        from datetime import datetime

        year_match = re.search(r'(20\d{2})', question)
        year_value = int(year_match.group(1)) if year_match else datetime.now().year
        for month_name, month_number in resident_month_lookup.items():
            if month_name in question:
                reference_month = month_number + 1
                reference_year = year_value
                if reference_month == 13:
                    reference_month = 1
                    reference_year += 1
                return {
                    'label': f"{resident_month_names[month_number]} {year_value}",
                    'reference_date': f"{reference_year}-{reference_month:02d}-01",
                }
        return None

    def _build_resident_help_answer(question: str, context: dict):
        from datetime import datetime
        import reports as financial_reports

        normalized_question = " ".join((question or '').strip().lower().split())
        if not normalized_question:
            return None

        month_reference = _extract_resident_month_reference(normalized_question)
        totals = context['resident_totals']
        company_info = context['company_info']

        if 'foto' in normalized_question or 'perfil' in normalized_question:
            return {
                'tone': 'primary',
                'title': 'Actualizar foto o perfil',
                'body': 'Puedes actualizar tu foto, nombre y telefono desde Mi Perfil dentro del portal.',
                'detail': 'Abre el editor de perfil, carga la imagen y guarda los cambios.',
                'link_url': url_for('auth.edit_profile'),
                'link_label': 'Abrir Mi Perfil',
            }

        if 'contrase' in normalized_question or 'clave' in normalized_question:
            return {
                'tone': 'warning',
                'title': 'Cambiar contrasena',
                'body': 'El cambio de contrasena se realiza desde la opcion de seguridad del portal.',
                'detail': 'Debes confirmar tu contrasena actual antes de guardar la nueva.',
                'link_url': url_for('auth.change_password'),
                'link_label': 'Cambiar contrasena',
            }

        if 'factura' in normalized_question and ('pendient' in normalized_question or 'debo' in normalized_question or 'por pagar' in normalized_question):
            pending_count = int(totals.get('pending_invoices') or 0)
            pending_balance = totals.get('balance') or 0
            if pending_count == 0:
                body = 'No tienes facturas pendientes en este momento.'
                detail = 'Tu cuenta se encuentra al dia en las unidades vinculadas.'
            else:
                body = f"Tienes {pending_count} factura(s) pendiente(s) por {_format_resident_currency(pending_balance)}."
                detail = 'En la seccion Facturas y pagos puedes revisar conceptos, fechas y descargar PDFs.'
            return {
                'tone': 'success' if pending_count == 0 else 'warning',
                'title': 'Estado de facturas pendientes',
                'body': body,
                'detail': detail,
                'link_url': url_for('resident_billing_overview'),
                'link_label': 'Ir a Facturas y pagos',
            }

        if month_reference and ('gasto' in normalized_question or 'gastos' in normalized_question):
            reference_dt = datetime.strptime(month_reference['reference_date'], '%Y-%m-%d')
            report_data = financial_reports.get_monthly_financial_report_data(
                reference_dt=reference_dt,
                period_mode='previous_month',
            )
            return {
                'tone': 'primary',
                'title': f"Gastos de {month_reference['label']}",
                'body': f"Los gastos operativos publicados fueron {_format_resident_currency(report_data.get('total_expenses'))}.",
                'detail': (
                    f"Cobros reportados: {_format_resident_currency(report_data.get('total_collections'))}. "
                    f"Balance de cierre: {_format_resident_currency(report_data.get('closing_balance'))}."
                ),
                'link_url': url_for(
                    'reports.monthly_preview_pdf',
                    reference_date=month_reference['reference_date'],
                    period_mode='previous_month',
                ),
                'link_label': 'Abrir reporte mensual',
            }

        if month_reference and ('balance' in normalized_question or 'saldo' in normalized_question or 'reporte' in normalized_question):
            reference_dt = datetime.strptime(month_reference['reference_date'], '%Y-%m-%d')
            report_data = financial_reports.get_monthly_financial_report_data(
                reference_dt=reference_dt,
                period_mode='previous_month',
            )
            return {
                'tone': 'primary',
                'title': f"Balance del reporte de {month_reference['label']}",
                'body': f"El balance de cierre publicado fue {_format_resident_currency(report_data.get('closing_balance'))}.",
                'detail': (
                    f"Ingresos cobrados: {_format_resident_currency(report_data.get('total_collections'))}. "
                    f"Gastos: {_format_resident_currency(report_data.get('total_expenses'))}."
                ),
                'link_url': url_for(
                    'reports.monthly_preview_pdf',
                    reference_date=month_reference['reference_date'],
                    period_mode='previous_month',
                ),
                'link_label': 'Ver PDF del reporte',
            }

        if 'saldo actual' in normalized_question or 'balance actual' in normalized_question or (
            ('saldo' in normalized_question or 'balance' in normalized_question) and not month_reference
        ):
            return {
                'tone': 'primary',
                'title': 'Balance actual de tu cuenta',
                'body': f"Tu balance pendiente actual es {_format_resident_currency(totals.get('balance'))}.",
                'detail': (
                    f"Pagos registrados: {_format_resident_currency(totals.get('total_paid'))}. "
                    f"Facturas pendientes: {int(totals.get('pending_invoices') or 0)}."
                ),
                'link_url': url_for('resident_balances'),
                'link_label': 'Abrir Balances',
            }

        if 'reporte' in normalized_question:
            latest_report = context['report_months'][0] if context['report_months'] else None
            if latest_report:
                return {
                    'tone': 'primary',
                    'title': 'Ultimo reporte disponible',
                    'body': f"El ultimo reporte mensual completo disponible es {latest_report['label']}.",
                    'detail': 'Tambien tienes disponible un reporte actualizado del mes en curso dentro de la seccion Reportes.',
                    'link_url': url_for(
                        'reports.monthly_preview_pdf',
                        reference_date=latest_report['ref_date'],
                        period_mode='previous_month',
                    ),
                    'link_label': 'Abrir ultimo reporte',
                }

        if 'telefono' in normalized_question or 'correo' in normalized_question or 'contact' in normalized_question or 'administracion' in normalized_question:
            contact_lines = []
            if company_info.get('phone'):
                contact_lines.append(f"Telefono: {company_info['phone']}")
            if company_info.get('email'):
                contact_lines.append(f"Correo: {company_info['email']}")
            if company_info.get('name'):
                contact_lines.insert(0, f"Contacto principal: {company_info['name']}")
            return {
                'tone': 'info',
                'title': 'Contacto de administracion',
                'body': 'Puedes comunicarte con la administracion usando los datos registrados en el portal.',
                'detail': ' | '.join(contact_lines) if contact_lines else 'La administracion no tiene informacion de contacto completa en este momento.',
                'link_url': url_for('resident_help'),
                'link_label': 'Ver centro de ayuda',
            }

        return {
            'tone': 'secondary',
            'title': 'Pregunta lista para responderse',
            'body': 'Todavia no tengo una respuesta automatica para esa consulta dentro del portal.',
            'detail': 'Prueba preguntas sobre perfil, facturas pendientes, saldo actual, balance de un mes o gastos publicados.',
            'link_url': url_for('resident_help'),
            'link_label': 'Intentar otra pregunta',
        }

    def _sanitize_resident_help_text(value: Any, max_length: int = 700) -> str:
        normalized = " ".join(str(value or '').strip().split())
        if len(normalized) <= max_length:
            return normalized
        return normalized[: max_length - 3].rstrip() + '...'

    def _resident_help_thread_key() -> str:
        return f"resident_help_thread_{current_user.id}"

    def _serialize_resident_help_message(message: dict[str, Any]) -> dict[str, str]:
        role = 'assistant' if message.get('role') == 'assistant' else 'user'
        return {
            'role': role,
            'title': _sanitize_resident_help_text(message.get('title'), 120),
            'content': _sanitize_resident_help_text(message.get('content'), 900),
            'detail': _sanitize_resident_help_text(message.get('detail'), 280),
            'tone': _sanitize_resident_help_text(message.get('tone'), 24) or ('primary' if role == 'assistant' else 'secondary'),
            'source': _sanitize_resident_help_text(message.get('source'), 24) or ('rules' if role == 'assistant' else 'user'),
            'link_url': str(message.get('link_url') or '')[:500],
            'link_label': _sanitize_resident_help_text(message.get('link_label'), 60),
        }

    def _get_resident_help_thread() -> list[dict[str, str]]:
        raw_thread = session.get(_resident_help_thread_key()) or []
        if not isinstance(raw_thread, list):
            return []
        return [
            _serialize_resident_help_message(item)
            for item in raw_thread[-8:]
            if isinstance(item, dict)
        ]

    def _store_resident_help_thread(thread: list[dict[str, Any]]):
        session[_resident_help_thread_key()] = [
            _serialize_resident_help_message(item)
            for item in thread[-8:]
            if isinstance(item, dict)
        ]
        session.modified = True

    def _clear_resident_help_thread():
        session.pop(_resident_help_thread_key(), None)
        session.modified = True

    def _resident_ai_enabled() -> bool:
        return bool(
            app.config.get('RESIDENT_AI_CHAT_ENABLED')
            and app.config.get('RESIDENT_AI_API_URL')
            and app.config.get('RESIDENT_AI_API_KEY')
            and app.config.get('RESIDENT_AI_MODEL')
        )

    def _build_resident_ai_context_text(question: str, context: dict, deterministic_answer: Optional[dict]) -> str:
        from datetime import datetime
        import reports as financial_reports

        totals = context.get('resident_totals') or {}
        company_info = context.get('company_info') or {}
        report_months = context.get('report_months') or []
        pending_preview = context.get('pending_preview') or []
        month_reference = _extract_resident_month_reference(question.lower())

        lines = [
            f"Residente: {current_user.full_name or current_user.username}",
            f"Balance actual: {_format_resident_currency(totals.get('balance'))}",
            f"Pagos registrados: {_format_resident_currency(totals.get('total_paid'))}",
            f"Facturas pendientes: {int(totals.get('pending_invoices') or 0)}",
            f"Unidades vinculadas: {int(totals.get('apartments') or 0)}",
        ]

        resident_units = context.get('resident_units') or []
        if resident_units:
            lines.append('Resumen por unidad:')
            for unit in resident_units[:4]:
                apartment_number = unit.get('apartment_number') or unit.get('unit_id') or 'N/D'
                lines.append(
                    f"- Apto {apartment_number}: balance {_format_resident_currency(unit.get('balance'))}, "
                    f"pagado {_format_resident_currency(unit.get('total_paid'))}, "
                    f"facturas pendientes {int(unit.get('pending_invoices') or 0)}"
                )

        if pending_preview:
            lines.append('Facturas pendientes recientes:')
            for invoice in pending_preview[:3]:
                lines.append(
                    f"- {invoice.get('description') or 'Factura'} | Apto {invoice.get('apartment_number') or invoice.get('unit_id') or 'N/D'} | "
                    f"Monto {_format_resident_currency(invoice.get('remaining') or invoice.get('amount'))} | "
                    f"Vence {invoice.get('due_date') or 'sin fecha'}"
                )

        if report_months:
            lines.append(
                "Reportes historicos disponibles: " + ", ".join(month['label'] for month in report_months[:4])
            )

        if month_reference:
            try:
                reference_dt = datetime.strptime(month_reference['reference_date'], '%Y-%m-%d')
                report_data = financial_reports.get_monthly_financial_report_data(
                    reference_dt=reference_dt,
                    period_mode='previous_month',
                )
                lines.append(
                    f"Reporte consultado {month_reference['label']}: cobros {_format_resident_currency(report_data.get('total_collections'))}, "
                    f"gastos {_format_resident_currency(report_data.get('total_expenses'))}, "
                    f"balance {_format_resident_currency(report_data.get('closing_balance'))}."
                )
            except Exception as exc:
                app.logger.warning(f"No se pudo preparar contexto de reporte para residente: {exc}")

        if company_info:
            contact_chunks = []
            if company_info.get('name'):
                contact_chunks.append(f"Contacto: {company_info['name']}")
            if company_info.get('phone'):
                contact_chunks.append(f"Telefono: {company_info['phone']}")
            if company_info.get('email'):
                contact_chunks.append(f"Correo: {company_info['email']}")
            if contact_chunks:
                lines.append(' | '.join(contact_chunks))

        if deterministic_answer:
            lines.append('Respuesta validada por las reglas actuales del portal:')
            lines.append(f"- Titulo: {deterministic_answer.get('title') or 'Sin titulo'}")
            lines.append(f"- Cuerpo: {deterministic_answer.get('body') or ''}")
            if deterministic_answer.get('detail'):
                lines.append(f"- Detalle: {deterministic_answer['detail']}")

        return "\n".join(lines)

    def _build_resident_ai_answer(
        question: str,
        context: dict,
        thread: list[dict[str, str]],
        deterministic_answer: Optional[dict],
    ) -> Optional[dict]:
        if not _resident_ai_enabled():
            return None

        context_block = _build_resident_ai_context_text(question, context, deterministic_answer)
        messages = [
            {
                'role': 'system',
                'content': (
                    'Eres el asistente del portal residente Toscana. Responde solo con la informacion proporcionada, '
                    'sin inventar datos, montos ni estados. Si falta informacion, dilo claramente y sugiere contactar '
                    'a la administracion. Responde en espanol, con tono claro, concreto y en maximo 4 frases.'
                ),
            },
            {
                'role': 'system',
                'content': f'Contexto verificado del residente:\n{context_block}',
            },
        ]

        for item in thread[-4:]:
            role = 'assistant' if item.get('role') == 'assistant' else 'user'
            content_parts = []
            if role == 'assistant' and item.get('title'):
                content_parts.append(item['title'])
            if item.get('content'):
                content_parts.append(item['content'])
            if item.get('detail'):
                content_parts.append(item['detail'])
            content = "\n".join(content_parts).strip()
            if content:
                messages.append({'role': role, 'content': content[:700]})

        messages.append({'role': 'user', 'content': question})

        try:
            response = requests.post(
                app.config['RESIDENT_AI_API_URL'],
                headers={
                    'Authorization': f"Bearer {app.config['RESIDENT_AI_API_KEY']}",
                    'Content-Type': 'application/json',
                },
                json={
                    'model': app.config['RESIDENT_AI_MODEL'],
                    'messages': messages,
                    'temperature': 0.2,
                    'max_tokens': 280,
                },
                timeout=app.config['RESIDENT_AI_TIMEOUT_SECONDS'],
            )
            response.raise_for_status()
            payload = response.json()
            choices = payload.get('choices') or []
            ai_text = ''
            if choices:
                ai_text = ((choices[0].get('message') or {}).get('content') or '').strip()
            ai_text = _sanitize_resident_help_text(ai_text, 900)
            if not ai_text:
                return None
        except requests.RequestException as exc:
            app.logger.warning(f"Asistente IA residente no disponible: {exc}")
            return None
        except ValueError as exc:
            app.logger.warning(f"Respuesta invalida del asistente IA residente: {exc}")
            return None

        answer_title = 'Respuesta del asistente Toscana IA'
        if deterministic_answer and deterministic_answer.get('title') != 'Pregunta lista para responderse':
            answer_title = deterministic_answer.get('title') or answer_title

        answer_detail = 'Respuesta generada con IA usando tu contexto validado y los reportes publicados.'
        if deterministic_answer and deterministic_answer.get('detail'):
            answer_detail = deterministic_answer['detail']

        return {
            'source': 'ai',
            'tone': (deterministic_answer or {}).get('tone') or 'primary',
            'title': answer_title,
            'body': ai_text,
            'detail': answer_detail,
            'link_url': (deterministic_answer or {}).get('link_url'),
            'link_label': (deterministic_answer or {}).get('link_label'),
        }

    def _compose_resident_help_answer(question: str, context: dict, thread: list[dict[str, str]]) -> Optional[dict]:
        deterministic_answer = _build_resident_help_answer(question, context)
        ai_answer = _build_resident_ai_answer(question, context, thread, deterministic_answer)
        return ai_answer or deterministic_answer

    def _resident_help_answer_to_message(answer: Optional[dict]) -> Optional[dict[str, str]]:
        if not answer:
            return None
        return _serialize_resident_help_message({
            'role': 'assistant',
            'title': answer.get('title'),
            'content': answer.get('body'),
            'detail': answer.get('detail'),
            'tone': answer.get('tone'),
            'source': answer.get('source') or 'rules',
            'link_url': answer.get('link_url'),
            'link_label': answer.get('link_label'),
        })

    def _build_resident_help_context(question: str = '', thread: Optional[list[dict[str, str]]] = None):
        context = _get_resident_common_context()
        resident_help_thread = thread if thread is not None else _get_resident_help_thread()
        latest_answer = next(
            (message for message in reversed(resident_help_thread) if message.get('role') == 'assistant'),
            None,
        )
        context.update({
            'pending_preview': residents.list_resident_invoices_for_user(
                current_user.id,
                fallback_email=current_user.email,
                paid=False,
                limit=3,
            ),
            'resident_help_question': question,
            'resident_help_answer': latest_answer,
            'resident_help_thread': resident_help_thread,
            'resident_ai_enabled': _resident_ai_enabled(),
            'resident_ai_status_label': 'IA conectada' if _resident_ai_enabled() else 'Asistente guiado',
            'resident_ai_status_detail': (
                'Usa un modelo externo con contexto validado del portal y reportes publicados.'
                if _resident_ai_enabled()
                else 'Responde con logica del portal y datos verificados hasta que configures la IA externa.'
            ),
            'resident_help_suggestions': [
                'Donde puedo actualizar mi foto de perfil?',
                'Cuantas facturas pendientes tengo?',
                'Cual es mi saldo actual?',
                'Cuales fueron los gastos de abril 2026?',
                'Cual fue el balance del reporte de mayo 2026?',
                'Resumeme mis pagos mas recientes y dime si tengo deuda activa.',
            ],
        })
        return context

    def _render_resident_page(template_name: str, section: str, section_context: dict):
        context = dict(section_context)
        context['resident_active_section'] = section
        return render_template(template_name, **context)
    
    @app.route("/dashboard/balances")
    @login_required
    def resident_balances():
        if current_user.role != 'resident':
            return redirect(url_for('dashboard'))
        return _render_resident_page(
            'resident_balances.html',
            'balances',
            _build_resident_balances_context(),
        )

    @app.route("/dashboard/evolucion")
    @login_required
    def resident_evolution():
        if current_user.role != 'resident':
            return redirect(url_for('dashboard'))
        return _render_resident_page(
            'resident_evolution.html',
            'evolution',
            _build_resident_evolution_context(),
        )

    @app.route("/dashboard/facturas-pagos")
    @login_required
    def resident_billing_overview():
        if current_user.role != 'resident':
            return redirect(url_for('dashboard'))
        return _render_resident_page(
            'resident_billing.html',
            'billing',
            _build_resident_billing_context(),
        )

    @app.route("/dashboard/reportes")
    @login_required
    def resident_reports():
        if current_user.role != 'resident':
            return redirect(url_for('dashboard'))
        return _render_resident_page(
            'resident_reports.html',
            'reports',
            _build_resident_reports_context(),
        )

    @app.route("/dashboard/ayuda", methods=['GET', 'POST'])
    @login_required
    def resident_help():
        if current_user.role != 'resident':
            return redirect(url_for('dashboard'))
        action = (request.form.get('action') or request.args.get('action') or '').strip().lower()
        if action == 'reset':
            _clear_resident_help_thread()
            return redirect(url_for('resident_help'))

        resident_thread = _get_resident_help_thread()

        if request.method == 'POST':
            resident_question = (request.form.get('question') or '').strip()
            if resident_question:
                resident_context = _build_resident_help_context('', resident_thread)
                resident_answer = _compose_resident_help_answer(resident_question, resident_context, resident_thread)
                resident_thread.append(_serialize_resident_help_message({
                    'role': 'user',
                    'content': resident_question,
                }))
                assistant_message = _resident_help_answer_to_message(resident_answer)
                if assistant_message:
                    resident_thread.append(assistant_message)
                _store_resident_help_thread(resident_thread)
            return redirect(url_for('resident_help'))

        resident_question = (request.args.get('q') or '').strip()
        if resident_question:
            resident_context = _build_resident_help_context('', resident_thread)
            resident_answer = _compose_resident_help_answer(resident_question, resident_context, resident_thread)
            preview_thread = resident_thread + [_serialize_resident_help_message({
                'role': 'user',
                'content': resident_question,
            })]
            assistant_message = _resident_help_answer_to_message(resident_answer)
            if assistant_message:
                preview_thread.append(assistant_message)
            return _render_resident_page(
                'resident_help.html',
                'help',
                _build_resident_help_context(resident_question, preview_thread),
            )

        return _render_resident_page(
            'resident_help.html',
            'help',
            _build_resident_help_context('', resident_thread),
        )

    @app.route("/dashboard")
    @login_required
    def dashboard():
        """Dashboard principal con acciones rápidas y resumen."""
        if current_user.role == 'resident':
            return resident_balances()
        from datetime import datetime, timedelta
        import models
        import apartments
        import products_services
        import suppliers
        
        stats = {
            'units_count': 0,
            'cash_available': 0,
            'unpaid_count': 0,
            'total_pending': 0,
            'total_invoiced': 0,
            'total_paid': 0,
            'invoice_status': {'paid': 0, 'unpaid': 0},
            'recent_invoices': [],
            'recent_payments': [],
            'clients': [],
            'services': [],
            'suppliers': [],
            'pending_invoices': [],
        }
        
        try:
            conn = db.get_conn()
            cur = conn.cursor()
            
            # Apartamentos
            apts = apartments.list_apartments()
            stats['units_count'] = len(apts)
            
            # Facturas
            invoices = models.list_invoices()
            paid_count = sum(1 for i in invoices if i.get('paid'))
            unpaid_count = len(invoices) - paid_count
            stats['invoice_status'] = {'paid': paid_count, 'unpaid': unpaid_count}
            stats['unpaid_count'] = unpaid_count
            
            total_invoiced = sum(i.get('amount', 0) for i in invoices)
            stats['total_invoiced'] = total_invoiced
            
            # Total pagado
            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments")
            total_paid = cur.fetchone()[0]
            stats['total_paid'] = total_paid
            stats['total_pending'] = total_invoiced - total_paid
            
            # Efectivo disponible (pagos + ingresos contables - gastos)
            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments")
            total_income = cur.fetchone()[0]
            # Sumar ingresos de accounting_transactions que NO son duplicados de pagos (INV-*)
            cur.execute("""SELECT COALESCE(SUM(amount), 0) FROM accounting_transactions 
                           WHERE type = 'income' AND (reference IS NULL OR reference NOT LIKE 'INV-%')""")
            total_income += cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses")
            total_expenses = cur.fetchone()[0]
            stats['cash_available'] = total_income - total_expenses
            
            # Facturas recientes (últimas 5)
            stats['recent_invoices'] = invoices[:5] if invoices else []
            
            # Pagos recientes (últimos 5)
            cur.execute("""
                SELECT p.*, i.description as invoice_desc, a.number as apt_number,
                       a.resident_name
                FROM payments p
                JOIN invoices i ON p.invoice_id = i.id
                LEFT JOIN apartments a ON i.unit_id = a.id
                ORDER BY p.paid_date DESC LIMIT 5
            """)
            stats['recent_payments'] = [dict(r) for r in cur.fetchall()]
            
            # Clientes (apartamentos con residentes) para wizards
            clients = []
            for apt in apts:
                if apt.get('resident_name'):
                    clients.append({
                        'id': apt['id'],
                        'name': apt['resident_name'],
                        'apartment': apt['number'],
                        'email': apt.get('resident_email', ''),
                        'phone': apt.get('resident_phone', ''),
                    })
            stats['clients'] = clients
            
            # Servicios activos
            svcs = products_services.list_products_services(active_only=True)
            stats['services'] = [{'id': s['id'], 'code': s.get('code',''), 'name': s['name'],
                                   'price': s.get('price',0)} for s in svcs]
            
            # Proveedores
            sups = suppliers.list_suppliers()
            stats['suppliers'] = [{'id': s['id'], 'name': s['name'],
                                    'type': s.get('supplier_type',''),
                                    'phone': s.get('phone',''),
                                    'email': s.get('email','')} for s in sups]
            
            # Facturas pendientes con balance
            cur.execute("""
                SELECT i.id, i.description, i.amount, i.issued_date, i.unit_id,
                       a.resident_name as client_name, a.number as apartment_number,
                       COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as total_paid
                FROM invoices i
                LEFT JOIN apartments a ON i.unit_id = a.id
                WHERE i.paid = 0
                ORDER BY i.id DESC
            """)
            pending = [dict(r) for r in cur.fetchall()]
            for pi in pending:
                pi['remaining'] = max(pi['amount'] - pi['total_paid'], 0)
            stats['pending_invoices'] = pending
            
            conn.close()
        except Exception as e:
            app.logger.error(f"Error loading dashboard: {e}")
        
        stats['now'] = datetime.now().strftime('%Y-%m-%d')
        return render_template("index.html", **stats)
    
    @app.route("/health")
    def health_check():
        """Endpoint para verificar el estado de la aplicación."""
        status = {
            'status': 'healthy',
            'database': 'unknown'
        }
        
        try:
            # Verificar conexión a BD
            conn = db.get_conn()
            conn.execute("SELECT 1")
            conn.close()
            status['database'] = 'connected'
        except Exception as e:
            status['database'] = 'error'
            status['status'] = 'unhealthy'
            status['error'] = str(e)
        
        status_code = 200 if status['status'] == 'healthy' else 503
        return jsonify(status), status_code


def _register_error_handlers(app: Flask) -> None:
    """Registra los manejadores de errores HTTP."""
    
    @app.errorhandler(400)
    def bad_request_error(error):
        app.logger.warning(f"Bad request: {error}")
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(403)
    def forbidden_error(error):
        app.logger.warning(f"Forbidden: {error}")
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal error: {error}", exc_info=True)
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        """Manejador genérico de excepciones."""
        app.logger.error(f"Unhandled exception: {error}", exc_info=True)
        
        if app.debug:
            raise error
        
        return render_template('errors/500.html'), 500


def _register_security_headers(app: Flask) -> None:
    """Registra headers de seguridad en todas las respuestas."""
    
    @app.after_request
    def add_security_headers(response):
        """Agrega headers de seguridad a cada respuesta."""
        # Prevenir sniffing de MIME type
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Proteccion contra clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        
        # Proteccion XSS (legacy, pero aun util)
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions policy (limitar APIs del navegador)
        # camera=(self) permite acceso a la cámara para OCR en móviles
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=(self)'
        
        # Content Security Policy basica (ajustar segun necesidades)
        # Permite inline styles/scripts por Bootstrap, ajustar en produccion
        if not app.debug:
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
                "font-src 'self' cdn.jsdelivr.net; "
                "img-src 'self' data:; "
                "connect-src 'self'"
            )
            response.headers['Content-Security-Policy'] = csp
        
        return response


# Crear instancia de la aplicación
app = create_app()


# Entry point principal
if __name__ == "__main__":
    HOST = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
    PORT = int(os.environ.get("FLASK_RUN_PORT", 5000))
    DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"
    
    print(f"{'='*50}")
    print(f"  Building Maintenance System")
    print(f"{'='*50}")
    print(f"  Servidor: http://{HOST}:{PORT}")
    print(f"  Debug mode: {DEBUG}")
    print(f"  Base de datos: {db.DB_PATH}")
    print(f"{'='*50}\n")
    
    app.run(host=HOST, port=PORT, debug=DEBUG)