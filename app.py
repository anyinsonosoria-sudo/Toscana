"""
Aplicación principal Flask para gestión de edificios.
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

from flask import Flask, redirect, url_for, render_template, jsonify
from flask_login import current_user, login_required

import db
import company
import customization
from extensions import init_extensions
from auth import auth_bp
from blueprints.settings import settings_bp
from blueprints.company import company_bp
from blueprints.apartments import apartments_bp
from blueprints.billing import billing_bp
from blueprints.accounting import accounting_bp
from blueprints.expenses import expenses_bp
from blueprints.products import products_bp
from blueprints.reports import reports_bp
from blueprints.suppliers import suppliers_bp


def create_app(config_object: str = None) -> Flask:
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
    
    @app.route("/dashboard")
    @login_required
    def dashboard():
        """Dashboard principal con acciones rápidas y resumen."""
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
            
            # Efectivo disponible (ingresos - gastos)
            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments")
            total_income = cur.fetchone()[0]
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
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
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