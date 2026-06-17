"""
Aplicación principal Flask para gestión de edificios.
"""
import os
import secrets
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import timedelta
from typing import Any, Optional
from dotenv import load_dotenv
import requests

# Cargar variables de entorno desde .env
load_dotenv()

from flask import Flask, redirect, url_for, render_template, jsonify, request, session, flash
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
    fallback_key = secrets.token_hex(32)
    app.config['SECRET_KEY'] = os.environ.get(
        'SECRET_KEY', 
        os.environ.get('FLASK_SECRET_KEY', fallback_key)
    )
    
    # Cargar configuración
    if config_object:
        app.config.from_object(config_object)
    else:
        try:
            from config import get_config
            app.config.from_object(get_config())
        except Exception as e:
            print(f"Error loading config: {e}")
    
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
        env_key = os.environ.get('SECRET_KEY') or os.environ.get('FLASK_SECRET_KEY')
        if not env_key or env_key == 'replace-this-with-a-secure-random-key':
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
                {
                    'endpoint': 'logout',
                    'label': 'Salir',
                    'icon': 'bi bi-box-arrow-right text-danger',
                    'url': '/logout',
                },
            ]

        return dict(get_resident_navigation=get_resident_navigation)
    
    @app.context_processor
    def inject_resident_totals():
        """Inyecta los totales del residente si está autenticado como tal."""
        if current_user.is_authenticated and current_user.role == 'resident':
            import residents
            try:
                summary = residents.get_resident_statement_summary_for_user(
                    current_user.id,
                    fallback_email=current_user.email,
                )
                return dict(resident_totals=summary.get('totals', {}))
            except Exception as e:
                app.logger.error(f"Error injecting resident totals: {e}")
        return dict(resident_totals={'balance': 0, 'total_paid': 0, 'apartments': 0})
    
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

    # ── Resident Portal (delegated to services.resident_help) ─────
    from services.resident_help import (
        build_balances_context,
        build_evolution_context,
        build_billing_context,
        build_reports_context,
        build_help_context,
        compose_help_answer,
        get_help_thread,
        store_help_thread,
        clear_help_thread,
        serialize_help_message,
        help_answer_to_message,
        render_resident_page,
    )

    @app.route("/dashboard/balances")
    @login_required
    def resident_balances():
        if current_user.role != 'resident':
            return redirect(url_for('dashboard'))
        return render_resident_page(
            'resident_balances.html', 'balances', build_balances_context(),
        )

    @app.route("/dashboard/evolucion")
    @login_required
    def resident_evolution():
        if current_user.role != 'resident':
            return redirect(url_for('dashboard'))
        return render_resident_page(
            'resident_evolution.html', 'evolution', build_evolution_context(),
        )

    @app.route("/dashboard/facturas-pagos")
    @login_required
    def resident_billing_overview():
        if current_user.role != 'resident':
            return redirect(url_for('dashboard'))
        return render_resident_page(
            'resident_billing.html', 'billing', build_billing_context(),
        )

    @app.route("/dashboard/reportes")
    @login_required
    def resident_reports():
        if current_user.role != 'resident':
            return redirect(url_for('dashboard'))
        return render_resident_page(
            'resident_reports.html', 'reports', build_reports_context(),
        )

    @app.route("/dashboard/ayuda", methods=['GET', 'POST'])
    @login_required
    def resident_help():
        if current_user.role != 'resident':
            return redirect(url_for('dashboard'))
        action = (request.form.get('action') or request.args.get('action') or '').strip().lower()
        if action == 'reset':
            clear_help_thread()
            return redirect(url_for('resident_help'))

        resident_thread = get_help_thread()

        if request.method == 'POST':
            resident_question = (request.form.get('question') or '').strip()
            if resident_question:
                resident_context = build_help_context('', resident_thread)
                resident_answer = compose_help_answer(resident_question, resident_context, resident_thread)
                resident_thread.append(serialize_help_message({
                    'role': 'user',
                    'content': resident_question,
                }))
                assistant_message = help_answer_to_message(resident_answer)
                if assistant_message:
                    resident_thread.append(assistant_message)
                store_help_thread(resident_thread)
            return redirect(url_for('resident_help'))

        resident_question = (request.args.get('q') or '').strip()
        if resident_question:
            resident_context = build_help_context('', resident_thread)
            resident_answer = compose_help_answer(resident_question, resident_context, resident_thread)
            preview_thread = resident_thread + [serialize_help_message({
                'role': 'user',
                'content': resident_question,
            })]
            assistant_message = help_answer_to_message(resident_answer)
            if assistant_message:
                preview_thread.append(assistant_message)
            return render_resident_page(
                'resident_help.html', 'help',
                build_help_context(resident_question, preview_thread),
            )

        return render_resident_page(
            'resident_help.html', 'help',
            build_help_context('', resident_thread),
        )

    @app.route("/dashboard/ayuda/api", methods=['POST'], endpoint='resident_help_api')
    @login_required
    def resident_help_api():
        """AJAX endpoint for immersive chat — returns JSON instead of rendering HTML."""
        from flask import jsonify
        if current_user.role != 'resident':
            return jsonify({'error': 'unauthorized'}), 403

        data = request.get_json(silent=True) or {}
        question = (data.get('question') or '').strip()
        if not question:
            return jsonify({'error': 'empty_question'}), 400

        resident_thread = get_help_thread()
        resident_context = build_help_context('', resident_thread)
        resident_answer = compose_help_answer(question, resident_context, resident_thread)

        # Store user message + assistant answer in thread
        resident_thread.append(serialize_help_message({
            'role': 'user',
            'content': question,
        }))
        assistant_message = help_answer_to_message(resident_answer)
        if assistant_message:
            resident_thread.append(assistant_message)
        store_help_thread(resident_thread)

        # Build response payload
        if assistant_message:
            return jsonify({'answer': assistant_message})
        return jsonify({'answer': None})

    @app.route("/dashboard/ayuda/debug", methods=['GET'], endpoint='resident_help_debug')
    @login_required
    def resident_help_debug():
        """Temporary diagnostic endpoint to debug Gemini configuration and API connectivity."""
        if current_user.role != 'resident':
            return jsonify({'error': 'unauthorized'}), 403

        from services.resident_help import ai_enabled
        import sys

        cfg = app.config
        debug_info = {
            'RESIDENT_AI_CHAT_ENABLED_cfg': cfg.get('RESIDENT_AI_CHAT_ENABLED'),
            'RESIDENT_AI_CHAT_ENABLED_env': os.environ.get('RESIDENT_AI_CHAT_ENABLED'),
            'RESIDENT_AI_API_KEY_configured': bool(cfg.get('RESIDENT_AI_API_KEY')),
            'RESIDENT_AI_MODEL': cfg.get('RESIDENT_AI_MODEL'),
            'ai_enabled_func': ai_enabled(),
            'python_version': sys.version,
        }

        # Attempt to import google-generativeai
        try:
            import google.generativeai as genai
            debug_info['import_generativeai'] = 'success'
        except ImportError as e:
            debug_info['import_generativeai'] = f'failed: {e}'
            return jsonify(debug_info)

        # Attempt test calls on both gemini-2.0-flash and gemini-1.5-flash
        genai.configure(api_key=cfg.get('RESIDENT_AI_API_KEY') or '')
        
        # Test 2.0 Flash
        try:
            model_20 = genai.GenerativeModel(model_name='gemini-2.0-flash')
            res_20 = model_20.generate_content("Hola, responde con la palabra 'OK'")
            debug_info['gemini_2.0_flash'] = f'success: {res_20.text.strip()}'
        except Exception as e:
            debug_info['gemini_2.0_flash'] = f'failed: {e}'

        # Test 1.5 Flash
        try:
            model_15 = genai.GenerativeModel(model_name='gemini-1.5-flash')
            res_15 = model_15.generate_content("Hola, responde con la palabra 'OK'")
            debug_info['gemini_1.5_flash'] = f'success: {res_15.text.strip()}'
        except Exception as e:
            debug_info['gemini_1.5_flash'] = f'failed: {e}'

        return jsonify(debug_info)

    @app.route("/dashboard/reportar_pago/<int:invoice_id>", methods=['POST'])
    @login_required
    def resident_report_payment(invoice_id):
        if current_user.role != 'resident':
            return redirect(url_for('dashboard'))
        
        from data_models.models import Invoice, ReportedPayment
        from extensions import db as sa_db
        
        invoice = sa_db.session.get(Invoice, invoice_id)
        if not invoice:
            flash("Factura no encontrada.", "error")
            return redirect(url_for('resident_billing_overview'))
            
        amount = request.form.get('amount', type=float)
        reference = request.form.get('reference', '').strip()
        
        if not amount or amount <= 0:
            flash("El monto debe ser mayor a 0.", "error")
            return redirect(url_for('resident_billing_overview'))
            
        reported_payment = ReportedPayment()
        reported_payment.invoice_id = invoice.id
        reported_payment.resident_id = current_user.id
        reported_payment.amount = amount
        reported_payment.reference = reference
        reported_payment.status = 'pending'
        sa_db.session.add(reported_payment)
        sa_db.session.commit()
        
        flash("Pago reportado exitosamente. Está pendiente de validación.", "success")
        return redirect(url_for('resident_billing_overview'))

    # ── Dashboard & Health ──────────────────────────────────────────
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
            with db.get_db() as conn:
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
        except Exception as e:
            app.logger.error(f"Error loading dashboard: {e}")
        
        stats['now'] = datetime.now().strftime('%Y-%m-%d')
        return render_template("index.html", **stats)

    resident_month_names = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
        7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    resident_month_short_names = {
        1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
    }
    resident_month_lookup = {v.lower(): k for k, v in resident_month_names.items()}

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

    def _normalize_resident_help_question(question: str) -> str:
        import re
        import unicodedata

        normalized = unicodedata.normalize('NFKD', question or '')
        normalized = normalized.encode('ascii', 'ignore').decode('ascii')
        normalized = re.sub(r'[^a-z0-9\s]+', ' ', normalized.lower())
        return ' '.join(normalized.split())

    def _resident_question_has_any(normalized_question: str, fragments: list[str]) -> bool:
        return any(fragment in normalized_question for fragment in fragments)

    def _is_followup_question(normalized_question: str) -> bool:
        """Returns True when the question references a previous answer rather than introducing a new topic."""
        followup_signals = [
            # Pronombres demostrativos
            'ese', 'eso', 'esa', 'esos', 'esas', 'esto', 'estos', 'estas',
            # Solicitudes de desglose
            'desglos', 'detalla', 'detalle de', 'dame mas', 'ampliar',
            'mas detalle', 'mas informacion', 'con mas detalle',
            'que incluye', 'que contiene', 'como se compone', 'que hay ahi',
            'del total', 'de eso', 'de ese', 'de esa', 'de esas', 'de esos',
            'por categoria', 'por concepto', 'en que consiste',
            'puedes desglosar', 'puedes explicar', 'puedes ampliar',
            'y cuanto', 'y cuales', 'cuales son esos', 'cuales fueron',
            # Preguntas conversacionales de seguimiento
            'explicame', 'por que', 'como asi', 'en que se gasto',
            'en que se uso', 'a que se debe', 'de donde sale',
            'de donde salio', 'como es eso', 'que paso con',
            'y el resto', 'algo mas', 'que mas', 'hay algo mas',
            'cuanto fue', 'cuando fue', 'quien', 'a quien',
            'y los demas', 'y las demas', 'continua', 'sigue',
            'y eso', 'pero', 'entonces',
        ]
        return _resident_question_has_any(normalized_question, followup_signals)

    def _extract_last_assistant_topic(thread: list) -> Optional[dict]:
        """Extracts the conversation topic and month reference from the last assistant message."""
        last_assistant = next(
            (msg for msg in reversed(thread) if msg.get('role') == 'assistant'),
            None,
        )
        if not last_assistant:
            return None

        raw_text = ' '.join(filter(None, [
            last_assistant.get('title', ''),
            last_assistant.get('content', ''),
            last_assistant.get('detail', ''),
        ]))
        norm = _normalize_resident_help_question(raw_text)

        topic: dict[str, Any] = {
            'type': None,
            'month_reference': None,
            'was_expenses': False,
            'was_collections': False,
        }

        month_ref = _extract_resident_month_reference(norm)
        if month_ref:
            topic['month_reference'] = month_ref

        if _resident_question_has_any(norm, ['gasto', 'egreso', 'cobro', 'ingreso', 'reporte', 'cierre', 'mensual', 'operativo']):
            topic['type'] = 'report'
            topic['was_expenses'] = _resident_question_has_any(norm, ['gasto', 'gastos', 'egreso', 'operativo'])
            topic['was_collections'] = _resident_question_has_any(norm, ['cobro', 'cobros', 'ingreso', 'ingresos', 'recaud'])
        elif _resident_question_has_any(norm, ['pago', 'abono', 'historial', 'movimiento']):
            topic['type'] = 'payments'
        elif _resident_question_has_any(norm, ['factura', 'balance', 'saldo', 'deuda', 'pendient']):
            topic['type'] = 'account'
        elif _resident_question_has_any(norm, ['apartamento', 'apartamento', 'vinculad', 'inmueble']):
            topic['type'] = 'units'
        elif _resident_question_has_any(norm, ['contacto', 'telefono', 'correo', 'administracion']):
            topic['type'] = 'contact'

        return topic if topic['type'] else None

    def _format_resident_short_date(date_value: str | None) -> str:
        from datetime import datetime

        if not date_value:
            return 'sin fecha'
        try:
            return datetime.strptime(date_value[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
        except ValueError:
            return date_value[:10]

    def _build_resident_help_payload(
        title: str,
        body: str,
        detail: str = '',
        tone: str = 'primary',
        link_url: str | None = None,
        link_label: str | None = None,
    ) -> dict[str, str | None]:
        return {
            'tone': tone,
            'title': title,
            'body': body,
            'detail': detail,
            'link_url': link_url,
            'link_label': link_label,
        }

    def _build_resident_account_help_answer(normalized_question: str, context: dict) -> dict[str, str | None]:
        totals = context['resident_totals']
        pending_preview = list(context.get('pending_preview') or [])
        pending_count = int(totals.get('pending_invoices') or 0)
        pending_balance = totals.get('balance') or 0

        if pending_count == 0:
            body = 'No tienes balance pendiente ni facturas vencidas en este momento.'
            detail = (
                f"Pagos registrados: {_format_resident_currency(totals.get('total_paid'))}. "
                'Tu cuenta se encuentra al dia en los apartamentos vinculados.'
            )
            tone = 'success'
        else:
            body = (
                f"Tu cuenta mantiene {pending_count} factura(s) pendiente(s) por "
                f"{_format_resident_currency(pending_balance)}."
            )
            detail_parts = [
                f"Pagos registrados: {_format_resident_currency(totals.get('total_paid'))}."
            ]
            if pending_preview:
                detail_parts.append(
                    'Pendientes recientes: ' + '; '.join(
                        f"{invoice.get('description') or 'Factura'} "
                        f"(Apto {invoice.get('apartment_number') or invoice.get('unit_id') or 'N/D'})"
                        for invoice in pending_preview[:3]
                    )
                )
            detail = ' '.join(detail_parts)
            tone = 'warning'

        invoice_specific = _resident_question_has_any(
            normalized_question,
            ['factura', 'facturas', 'recibo', 'recibos', 'pendient', 'vencid', 'por pagar'],
        )
        balance_specific = _resident_question_has_any(
            normalized_question,
            ['saldo', 'balance', 'deuda', 'adeud', 'debo', 'mora', 'cuenta'],
        )
        if invoice_specific and not balance_specific:
            title = 'Estado de facturas pendientes'
        elif balance_specific and not invoice_specific:
            title = 'Balance actual de tu cuenta'
        else:
            title = 'Estado actual de tu cuenta'

        return _build_resident_help_payload(
            title=title,
            body=body,
            detail=detail,
            tone=tone,
            link_url=url_for('resident_billing_overview'),
            link_label='Ir a Facturas y pagos',
        )

    def _build_resident_payments_help_answer(context: dict) -> dict[str, str | None]:
        recent_payments = list(context.get('recent_payments') or [])
        if not recent_payments:
            return _build_resident_help_payload(
                title='Pagos recientes',
                body='Todavia no hay pagos registrados en tus apartamentos vinculados.',
                detail='Cuando registres pagos, aqui podras resumir los movimientos mas recientes y revisar el historial.',
                tone='info',
                link_url=url_for('resident_billing_overview'),
                link_label='Abrir historial de pagos',
            )

        recent_total = sum(float(payment.get('amount') or 0) for payment in recent_payments[:3])
        latest_payment = recent_payments[0]
        detail = 'Movimientos recientes: ' + '; '.join(
            f"{_format_resident_short_date(payment.get('paid_date'))}: "
            f"{_format_resident_currency(payment.get('amount'))} "
            f"via {(payment.get('method') or 'Sin especificar')}"
            for payment in recent_payments[:3]
        )
        if latest_payment.get('invoice_desc'):
            detail += f". Ultimo concepto: {latest_payment['invoice_desc']}"

        return _build_resident_help_payload(
            title='Pagos recientes',
            body=(
                f"Tus {len(recent_payments[:3])} pago(s) mas recientes suman "
                f"{_format_resident_currency(recent_total)}. El ultimo fue "
                f"{_format_resident_currency(latest_payment.get('amount'))} el "
                f"{_format_resident_short_date(latest_payment.get('paid_date'))}."
            ),
            detail=detail,
            tone='primary',
            link_url=url_for('resident_billing_overview'),
            link_label='Ver historial de pagos',
        )

    def _build_resident_units_help_answer(context: dict) -> dict[str, str | None]:
        resident_units = list(context.get('resident_units') or [])
        if not resident_units:
            return _build_resident_help_payload(
                title='Apartamentos vinculados',
                body='No se encontraron apartamentos vinculados a tu usuario en este momento.',
                detail='Si esperabas ver un apartamento aqui, revisa con administracion la vinculacion del residente.',
                tone='warning',
                link_url=url_for('resident_balances'),
                link_label='Volver al portal',
            )

        apartment_numbers = [
            str(unit.get('apartment_number') or unit.get('unit_id') or 'N/D') for unit in resident_units
        ]
        detail = 'Balance por apartamento: ' + '; '.join(
            f"Apto {unit.get('apartment_number') or unit.get('unit_id') or 'N/D'} "
            f"{_format_resident_currency(unit.get('balance'))}"
            for unit in resident_units[:4]
        )
        return _build_resident_help_payload(
            title='Tus apartamentos vinculados',
            body=(
                f"Tienes {len(resident_units)} apartamento(es) vinculada(s): "
                f"{', '.join(apartment_numbers[:6])}."
            ),
            detail=detail,
            tone='info',
            link_url=url_for('resident_balances'),
            link_label='Ver resumen por apartamento',
        )

    def _build_resident_report_help_answer(normalized_question: str, context: dict, wants_breakdown: bool = False, inherited_month: Optional[dict] = None, inherited_expenses: bool = False, inherited_collections: bool = False) -> dict[str, str | None]:
        from datetime import datetime
        import reports as financial_reports

        month_reference = _extract_resident_month_reference(normalized_question) or inherited_month
        wants_expenses = _resident_question_has_any(normalized_question, ['gasto', 'gastos', 'egreso', 'egresos', 'costo']) or inherited_expenses
        wants_collections = _resident_question_has_any(normalized_question, ['cobro', 'cobros', 'ingreso', 'ingresos', 'recaud']) or inherited_collections
        wants_balance = _resident_question_has_any(normalized_question, ['saldo', 'balance', 'cierre', 'resultado'])

        if not month_reference:
            latest_report = context['report_months'][0] if context.get('report_months') else None
            if not latest_report:
                return _build_resident_help_payload(
                    title='Reportes mensuales',
                    body='Todavia no hay reportes financieros publicados para tus consultas.',
                    detail='Cuando existan cierres mensuales, podras revisarlos desde la seccion Reportes.',
                    tone='info',
                    link_url=url_for('resident_reports'),
                    link_label='Abrir Reportes',
                )
            month_reference = {
                'label': latest_report['label'],
                'reference_date': latest_report['ref_date'],
                'period_mode': 'previous_month',
            }

        reference_dt = datetime.strptime(month_reference['reference_date'], '%Y-%m-%d')
        period_mode = month_reference.get('period_mode', 'previous_month')
        report_data = financial_reports.get_monthly_financial_report_data(
            reference_dt=reference_dt,
            period_mode=period_mode,
        )
        report_url = url_for(
            'reports.monthly_view_html',
            reference_date=month_reference['reference_date'],
            period_mode=period_mode,
        )

        if wants_expenses and not wants_collections and not wants_balance:
            if wants_breakdown:
                expense_items = report_data.get('expenses') or []
                if expense_items:
                    by_cat: dict[str, float] = {}
                    for item in expense_items:
                        cat = item.get('category') or 'Sin categoría'
                        by_cat[cat] = by_cat.get(cat, 0) + float(item.get('amount') or 0)
                    lines = [f"- {cat}: {_format_resident_currency(total)}" for cat, total in sorted(by_cat.items(), key=lambda x: -x[1])]
                    breakdown_detail = 'Desglose por categoría: ' + ' | '.join(lines[:8])
                else:
                    breakdown_detail = 'No hay ítems de gasto registrados para ese período.'
            else:
                breakdown_detail = (
                    f"Cobros reportados: {_format_resident_currency(report_data.get('total_collections'))}. "
                    f"Balance de cierre: {_format_resident_currency(report_data.get('closing_balance'))}."
                )
            return _build_resident_help_payload(
                title=f"Gastos de {month_reference['label']}",
                body=(
                    f"Los gastos operativos publicados fueron "
                    f"{_format_resident_currency(report_data.get('total_expenses'))}."
                ),
                detail=breakdown_detail,
                tone='primary',
                link_url=report_url,
                link_label='Abrir reporte mensual',
            )

        if wants_collections and not wants_expenses and not wants_balance:
            if wants_breakdown:
                collection_items = report_data.get('collections') or []
                if collection_items:
                    by_cat: dict[str, float] = {}
                    for item in collection_items:
                        cat = item.get('category') or item.get('payment_method') or 'Sin categoría'
                        by_cat[cat] = by_cat.get(cat, 0) + float(item.get('amount') or 0)
                    lines = [f"- {cat}: {_format_resident_currency(total)}" for cat, total in sorted(by_cat.items(), key=lambda x: -x[1])]
                    coll_detail = 'Desglose por categoría: ' + ' | '.join(lines[:8])
                else:
                    coll_detail = 'No hay cobros registrados para ese período.'
            else:
                coll_detail = (
                    f"Gastos: {_format_resident_currency(report_data.get('total_expenses'))}. "
                    f"Balance de cierre: {_format_resident_currency(report_data.get('closing_balance'))}."
                )
            return _build_resident_help_payload(
                title=f"Cobros de {month_reference['label']}",
                body=(
                    f"Los cobros publicados para ese periodo fueron "
                    f"{_format_resident_currency(report_data.get('total_collections'))}."
                ),
                detail=coll_detail,
                tone='primary',
                link_url=report_url,
                link_label='Ver PDF del reporte',
            )

        if wants_balance and month_reference:
            return _build_resident_help_payload(
                title=f"Balance del reporte de {month_reference['label']}",
                body=(
                    f"El balance de cierre publicado fue "
                    f"{_format_resident_currency(report_data.get('closing_balance'))}."
                ),
                detail=(
                    f"Cobros: {_format_resident_currency(report_data.get('total_collections'))}. "
                    f"Gastos: {_format_resident_currency(report_data.get('total_expenses'))}."
                ),
                tone='primary',
                link_url=report_url,
                link_label='Ver PDF del reporte',
            )

        return _build_resident_help_payload(
            title=f"Resumen del reporte de {month_reference['label']}",
            body=(
                f"El cierre publicado muestra balance "
                f"{_format_resident_currency(report_data.get('closing_balance'))}, "
                f"cobros {_format_resident_currency(report_data.get('total_collections'))} "
                f"y gastos {_format_resident_currency(report_data.get('total_expenses'))}."
            ),
            detail='Puedes abrir el PDF para revisar el detalle completo del periodo.',
            tone='primary',
            link_url=report_url,
            link_label='Abrir reporte mensual',
        )

    def _build_resident_contact_help_answer(context: dict) -> dict[str, str | None]:
        company_info = context['company_info']
        contact_lines = []
        if company_info.get('phone'):
            contact_lines.append(f"Telefono: {company_info['phone']}")
        if company_info.get('email'):
            contact_lines.append(f"Correo: {company_info['email']}")
        if company_info.get('name'):
            contact_lines.insert(0, f"Contacto principal: {company_info['name']}")
        return _build_resident_help_payload(
            title='Contacto de administracion',
            body='Puedes comunicarte con la administracion usando los datos registrados en el portal.',
            detail=' | '.join(contact_lines) if contact_lines else 'La administracion no tiene informacion de contacto completa en este momento.',
            tone='info',
            link_url=url_for('resident_help'),
            link_label='Ver centro de ayuda',
        )

    def _build_resident_capabilities_help_answer(context: dict) -> dict[str, str | None]:
        totals = context['resident_totals']
        return _build_resident_help_payload(
            title='Informacion disponible en tu portal',
            body=(
                'Puedo responder sobre saldo, facturas, pagos, apartamentos vinculados, '
                'reportes mensuales, perfil, clave y contacto de administracion usando solo la informacion de tu portal.'
            ),
            detail=(
                f"Ahora mismo tu cuenta muestra {_format_resident_currency(totals.get('balance'))} pendiente, "
                f"{int(totals.get('pending_invoices') or 0)} factura(s) pendiente(s) y "
                f"{int(totals.get('apartments') or 0)} apartamento(es) vinculada(s)."
            ),
            tone='info',
            link_url=url_for('resident_balances'),
            link_label='Abrir resumen del portal',
        )

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
                'reports.monthly_view_html',
                reference_date=datetime.now().strftime('%Y-%m-%d'),
                period_mode='current_month_to_date',
            ),
            'report_months': _build_resident_report_months(),
        })
        return context

    def _extract_resident_month_reference(question: str):
        import re
        from datetime import datetime, timedelta

        normalized_question = _normalize_resident_help_question(question)
        now = datetime.now()

        if any(fragment in normalized_question for fragment in ['este mes', 'mes actual', 'mes en curso', 'reporte actual']):
            return {
                'label': f"{resident_month_names[now.month]} {now.year}",
                'reference_date': now.strftime('%Y-%m-%d'),
                'period_mode': 'current_month_to_date',
            }

        if any(fragment in normalized_question for fragment in ['mes pasado', 'mes anterior', 'ultimo mes']):
            previous_month_anchor = (now.replace(day=1) - timedelta(days=1))
            return {
                'label': f"{resident_month_names[previous_month_anchor.month]} {previous_month_anchor.year}",
                'reference_date': now.strftime('%Y-%m-%d'),
                'period_mode': 'previous_month',
            }

        year_match = re.search(r'(20\d{2})', normalized_question)
        year_value = int(year_match.group(1)) if year_match else datetime.now().year
        for month_name, month_number in resident_month_lookup.items():
            if month_name in normalized_question:
                reference_month = month_number + 1
                reference_year = year_value
                if reference_month == 13:
                    reference_month = 1
                    reference_year += 1
                return {
                    'label': f"{resident_month_names[month_number]} {year_value}",
                    'reference_date': f"{reference_year}-{reference_month:02d}-01",
                    'period_mode': 'previous_month',
                }
        return None

    def _build_resident_help_answer(question: str, context: dict, thread: Optional[list] = None):
        normalized_question = _normalize_resident_help_question(question)
        if not normalized_question:
            return None

        wants_profile = _resident_question_has_any(
            normalized_question,
            ['foto', 'perfil', 'avatar', 'imagen', 'editar perfil', 'actualizar perfil', 'mis datos'],
        )
        wants_password = _resident_question_has_any(
            normalized_question,
            ['contrasen', 'clave', 'password', 'cambiar acceso', 'credencial'],
        )
        wants_account = _resident_question_has_any(
            normalized_question,
            ['saldo', 'balance', 'deuda', 'adeud', 'debo', 'pendient', 'por pagar', 'vencid', 'mora', 'factura', 'recibo', 'cuenta'],
        )
        wants_payments = _resident_question_has_any(
            normalized_question,
            ['pago', 'pagos', 'abono', 'abonos', 'historial', 'movimiento', 'movimientos', 'pagado', 'transfer', 'deposit'],
        )
        wants_units = _resident_question_has_any(
            normalized_question,
            ['apartamento', 'apartamentos', 'apto', 'apartamento', 'apartamentoes', 'vinculad', 'inmueble', 'inmuebles', 'propiedad'],
        )
        wants_reports = bool(_extract_resident_month_reference(normalized_question)) or _resident_question_has_any(
            normalized_question,
            ['reporte', 'reportes', 'informe', 'informes', 'mensual', 'gasto', 'gastos', 'egreso', 'egresos', 'cobro', 'cobros', 'ingreso', 'ingresos'],
        )
        wants_contact = _resident_question_has_any(
            normalized_question,
            ['telefono', 'correo', 'email', 'contact', 'administracion', 'soporte', 'oficina', 'whatsapp'],
        )
        wants_capabilities = _resident_question_has_any(
            normalized_question,
            ['que puedes', 'que informacion', 'que sabes', 'que puedo preguntar', 'como me puedes ayudar', 'ayuda del portal'],
        )

        sections = []

        if wants_profile:
            sections.append(_build_resident_help_payload(
                title='Actualizar foto o perfil',
                body='Puedes actualizar tu foto, nombre y telefono desde Mi Perfil dentro del portal.',
                detail='Abre el editor de perfil, carga la imagen y guarda los cambios.',
                tone='primary',
                link_url=url_for('auth.edit_profile'),
                link_label='Abrir Mi Perfil',
            ))

        if wants_password:
            sections.append(_build_resident_help_payload(
                title='Cambiar contrasena',
                body='El cambio de contrasena se realiza desde la opcion de seguridad del portal.',
                detail='Debes confirmar tu contrasena actual antes de guardar la nueva.',
                tone='warning',
                link_url=url_for('auth.change_password'),
                link_label='Cambiar contrasena',
            ))

        if wants_units:
            sections.append(_build_resident_units_help_answer(context))

        if wants_payments:
            sections.append(_build_resident_payments_help_answer(context))

        if wants_account:
            sections.append(_build_resident_account_help_answer(normalized_question, context))

        if wants_reports:
            sections.append(_build_resident_report_help_answer(normalized_question, context))

        if wants_contact:
            sections.append(_build_resident_contact_help_answer(context))

        if wants_capabilities and not sections:
            sections.append(_build_resident_capabilities_help_answer(context))

        # ── Follow-up inference ────────────────────────────────────────
        # When no direct intent matched and the question references a previous answer,
        # inherit the topic from the last assistant message.
        if not sections and thread and _is_followup_question(normalized_question):
            last_topic = _extract_last_assistant_topic(thread)
            if last_topic:
                wants_breakdown = True  # follow-up always implies more detail
                if last_topic['type'] == 'report':
                    sections.append(_build_resident_report_help_answer(
                        normalized_question,
                        context,
                        wants_breakdown=wants_breakdown,
                        inherited_month=last_topic.get('month_reference'),
                        inherited_expenses=last_topic.get('was_expenses', False),
                        inherited_collections=last_topic.get('was_collections', False),
                    ))
                elif last_topic['type'] == 'payments':
                    sections.append(_build_resident_payments_help_answer(context))
                elif last_topic['type'] == 'account':
                    sections.append(_build_resident_account_help_answer(normalized_question, context))
                elif last_topic['type'] == 'units':
                    sections.append(_build_resident_units_help_answer(context))
                elif last_topic['type'] == 'contact':
                    sections.append(_build_resident_contact_help_answer(context))
        # ── End follow-up inference ────────────────────────────────────

        if not sections:
            return _build_resident_capabilities_help_answer(context)

        if len(sections) == 1:
            return sections[0]

        detail_parts = [section.get('detail') for section in sections[:3] if section.get('detail')]
        tone = 'warning' if any(section.get('tone') == 'warning' for section in sections) else sections[0].get('tone', 'primary')
        primary_link = next((section for section in sections if section.get('link_url')), sections[0])
        return _build_resident_help_payload(
            title='Resumen de tu consulta',
            body=' '.join(section.get('body', '') for section in sections[:3] if section.get('body')),
            detail=' | '.join(detail_parts),
            tone=tone,
            link_url=primary_link.get('link_url'),
            link_label=primary_link.get('link_label') or 'Abrir detalle',
        )

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
            f"Apartamentos vinculados: {int(totals.get('apartments') or 0)}",
        ]

        resident_units = context.get('resident_units') or []
        if resident_units:
            lines.append('Resumen por apartamento:')
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
        deterministic_answer = _build_resident_help_answer(question, context, thread=thread)
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
        ai_enabled = _resident_ai_enabled()
        recent_payment_history: dict[str, Any] = residents.get_resident_payment_history_for_user(
            current_user.id,
            fallback_email=current_user.email,
            limit=3,
        )
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
            'recent_payments': list(recent_payment_history.get('items') or []),
            'resident_help_question': question,
            'resident_help_answer': latest_answer,
            'resident_help_thread': resident_help_thread,
            'resident_ai_enabled': ai_enabled,
            'resident_ai_status_label': 'IA conectada' if ai_enabled else 'Asistente guiado',
            'resident_ai_status_detail': (
                'Usa un modelo externo con contexto validado del portal y reportes publicados.'
                if ai_enabled
                else 'Responde con logica del portal y datos verificados hasta que configures la IA externa.'
            ),
            'resident_help_suggestions_label': 'Ejemplos de preguntas' if ai_enabled else 'Ejemplos que el portal ya responde bien',
            'resident_help_suggestions_hint': (
                'Puedes escribir cualquier pregunta sobre tu cuenta o los reportes; estas tarjetas son solo ideas.'
                if ai_enabled
                else 'Ahora mismo estas sugerencias coinciden con las categorias soportadas sin IA externa.'
            ),
            'resident_help_suggestions': (
                [
                    'Explicame mi balance actual.',
                    'Resumeme mis pagos mas recientes.',
                    'Tengo deuda activa este mes?',
                    'Que dice el ultimo reporte del residencial?',
                    'Como contacto a la administracion?',
                    'Donde cambio mi foto o mi clave?',
                ]
                if ai_enabled
                else [
                    'Donde puedo actualizar mi foto de perfil?',
                    'Cuantas facturas pendientes tengo?',
                    'Cual es mi saldo actual?',
                    'Cuales fueron los gastos de abril 2026?',
                    'Cual fue el balance del reporte de mayo 2026?',
                    'Como contacto a la administracion?',
                ]
            ),
        })
        return context

    def _render_resident_page(template_name: str, section: str, section_context: dict):
        context = dict(section_context)
        context['resident_active_section'] = section
        return render_template(template_name, **context)
    
    # Duplicate resident block removed.

    # Duplicated dashboard removed
    
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